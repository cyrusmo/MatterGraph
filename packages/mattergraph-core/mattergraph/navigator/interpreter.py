from __future__ import annotations

import re
from typing import Callable

from mattergraph.navigator.models import (
  Constraint,
  ConstraintKind,
  ConstraintOperator,
  ConstraintPlan,
  InterpretationResult,
  PropertyRegistry,
  UnresolvedConstraint,
)

INTERPRETER_VERSION = "deterministic-fallback-v1"

_ELEMENT_NAMES = {
  "aluminum": "Al",
  "aluminium": "Al",
  "cobalt": "Co",
  "copper": "Cu",
  "iron": "Fe",
  "lithium": "Li",
  "magnesium": "Mg",
  "manganese": "Mn",
  "nickel": "Ni",
  "nitrogen": "N",
  "oxygen": "O",
  "silicon": "Si",
  "sulfur": "S",
  "titanium": "Ti",
  "tungsten": "W",
  "vanadium": "V",
  "zinc": "Zn",
  "zirconium": "Zr",
}
_COUNT_WORDS = {
  "unary": 1,
  "binary": 2,
  "ternary": 3,
  "quaternary": 4,
  "quinary": 5,
}


class DeterministicInterpreter:
  """Bounded fallback parser used when the frozen Qwen runtime is unavailable.

  This parser is intentionally narrow. It emits unresolved requirements instead of mapping an
  unsupported scientific concept onto the nearest-looking indexed property.
  """

  def __init__(self, registry: PropertyRegistry) -> None:
    self.registry = registry
    self._constraint_counter = 0
    self._unresolved_counter = 0

  def interpret(self, text: str) -> InterpretationResult:
    self._constraint_counter = 0
    self._unresolved_counter = 0
    normalized = " ".join(text.strip().split())
    lower = normalized.lower()
    constraints: list[Constraint] = []
    unresolved: list[UnresolvedConstraint] = []

    include_elements, exclude_elements = self._elements(lower)
    if "oxide" in lower:
      include_elements.add("O")
    if "nitride" in lower:
      include_elements.add("N")
    if include_elements:
      constraints.append(self._constraint(
        field="elements",
        operator=ConstraintOperator.INCLUDE_ALL,
        value=sorted(include_elements),
        kind=ConstraintKind.CATEGORICAL,
        label="Include elements",
        source_text=normalized,
      ))
    if exclude_elements:
      constraints.append(self._constraint(
        field="elements",
        operator=ConstraintOperator.EXCLUDE_ANY,
        value=sorted(exclude_elements),
        kind=ConstraintKind.CATEGORICAL,
        label="Exclude elements",
        source_text=normalized,
      ))

    for word, count in _COUNT_WORDS.items():
      if re.search(rf"\b{word}\b", lower):
        constraints.append(self._constraint(
          field="nelements",
          operator=ConstraintOperator.EQ,
          value=count,
          unit="count",
          kind=ConstraintKind.CATEGORICAL,
          label=f"Exactly {count} elements",
          source_text=word,
        ))
        break

    self._numeric_constraint(
      lower,
      constraints,
      patterns=[
        r"(?:fewer|less) than\s+(?P<value>\d+)\s+(?:atomic\s+)?sites?",
        r"(?:sites?|atoms?)\s*(?:<|under|below)\s*(?P<value>\d+)",
      ],
      field="nsites",
      operator=ConstraintOperator.LT,
      unit="count",
      kind=ConstraintKind.CATEGORICAL,
      labeler=lambda value: f"Fewer than {int(value)} sites",
    )
    self._numeric_constraint(
      lower,
      constraints,
      patterns=[r"(?:at most|no more than|max(?:imum)?)\s+(?P<value>\d+)\s+(?:atomic\s+)?sites?"],
      field="nsites",
      operator=ConstraintOperator.LTE,
      unit="count",
      kind=ConstraintKind.CATEGORICAL,
      labeler=lambda value: f"At most {int(value)} sites",
    )
    self._numeric_constraint(
      lower,
      constraints,
      patterns=[
        r"density\s*(?:<|under|below|less than)\s*(?P<value>\d+(?:\.\d+)?)\s*g\s*/?\s*cm(?:\^?3|³)?",
      ],
      field="density",
      operator=ConstraintOperator.LT,
      unit="g/cm^3",
      kind=ConstraintKind.PHYSICAL,
      labeler=lambda value: f"Density below {value:g} g/cm³",
    )
    magnetization_match = re.search(
      r"magneti[sz]ation\s*(?:<|under|below|less than)\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>μb|ub)(?:\s*/\s*(?P<denom>site|cell))?",
      lower,
    )
    if magnetization_match:
      value = float(magnetization_match.group("value"))
      per_site = magnetization_match.group("denom") == "site"
      constraints.append(self._constraint(
        field=(
          "absolute_total_magnetization_per_site"
          if per_site
          else "absolute_total_magnetization"
        ),
        operator=ConstraintOperator.LT,
        value=value,
        unit="μB/site" if per_site else "μB/cell",
        kind=ConstraintKind.PHYSICAL,
        label=(
          f"Absolute net magnetization below {value:g} μB/site"
          if per_site
          else f"Absolute net cell magnetization below {value:g} μB/cell"
        ),
        source_text=magnetization_match.group(0),
      ))
    if "nonmagnetic" in lower or "non-magnetic" in lower:
      unresolved.append(self._unresolved(
        text="nonmagnetic",
        code="ambiguous_magnetic_semantics",
        reason=(
          "Nonmagnetic cannot be inferred from near-zero net magnetization; confirm net and "
          "reported local-moment thresholds."
        ),
        actions=[
          "confirm_net_magnetization_threshold",
          "confirm_net_and_local_moment_thresholds",
          "keep_unevaluated",
        ],
      ))

    self._numeric_constraint(
      lower,
      constraints,
      patterns=[
        r"(?:maximum|max)\s+force(?:\s+norm)?\s*(?:<|under|below)\s*(?P<value>\d+(?:\.\d+)?)\s*ev\s*/\s*(?:å|a|angstrom)",
      ],
      field="maximum_force_norm",
      operator=ConstraintOperator.LT,
      unit="eV/Å",
      kind=ConstraintKind.CALCULATION_QUALITY,
      labeler=lambda value: f"Maximum force below {value:g} eV/Å",
    )

    functional = re.search(r"\b(pbe|scan|pbesol|hse06)\b", lower)
    if functional:
      constraints.append(self._constraint(
        field="functional",
        operator=ConstraintOperator.EQ,
        value=functional.group(1),
        kind=ConstraintKind.CATEGORICAL,
        label=f"Functional: {functional.group(1).upper()}",
        source_text=functional.group(0),
        locked=True,
      ))

    unsupported = {
      "corrosion": "Corrosion resistance is not available in the frozen index.",
      "hardness": "Hardness is not available in the frozen index.",
      "toughness": "Fracture toughness is not available in the frozen index.",
      "conductivity": "Conductivity is not available in the frozen index.",
      "band gap": "Band gap is not available in index_v1.",
      "energy above hull": "Energy above hull is deferred from index_v1.",
    }
    for phrase, reason in unsupported.items():
      if phrase in lower:
        unresolved.append(self._unresolved(
          text=phrase,
          code="index_capability_mismatch",
          reason=reason,
          actions=["keep_unevaluated", "remove_after_confirmation", "export_data_request"],
        ))

    plan = ConstraintPlan(
      constraints=constraints,
      unresolved_constraints=unresolved,
      registry_version=self.registry.version,
      index_id=self.registry.index_id,
      interpreter_version=INTERPRETER_VERSION,
    )
    return InterpretationResult(
      plan=plan,
      interpreter={
        "id": INTERPRETER_VERSION,
        "kind": "deterministic_fallback",
        "model_used": False,
        "scientific_boundary": (
          "The fallback recognizes a bounded public grammar and leaves unsupported concepts unresolved."
        ),
      },
      confirmation_required=bool(constraints or unresolved),
    )

  def _constraint(
    self,
    *,
    field: str,
    operator: ConstraintOperator,
    value: float | int | str | bool | list[str],
    kind: ConstraintKind,
    label: str,
    source_text: str,
    unit: str | None = None,
    locked: bool = False,
  ) -> Constraint:
    self._constraint_counter += 1
    return Constraint(
      id=f"c{self._constraint_counter}",
      field=field,
      operator=operator,
      value=value,
      unit=unit,
      kind=kind,
      locked=locked,
      confirmed=False,
      label=label,
      source_text=source_text,
    )

  def _unresolved(
    self,
    *,
    text: str,
    code: str,
    reason: str,
    actions: list[str],
  ) -> UnresolvedConstraint:
    self._unresolved_counter += 1
    return UnresolvedConstraint(
      id=f"u{self._unresolved_counter}",
      text=text,
      code=code,
      reason=reason,
      actions=actions,
    )

  def _numeric_constraint(
    self,
    text: str,
    constraints: list[Constraint],
    *,
    patterns: list[str],
    field: str,
    operator: ConstraintOperator,
    unit: str,
    kind: ConstraintKind,
    labeler: Callable[[float], str],
  ) -> None:
    for pattern in patterns:
      match = re.search(pattern, text)
      if match:
        value = float(match.group("value"))
        numeric: float | int = int(value) if value.is_integer() else value
        constraints.append(self._constraint(
          field=field,
          operator=operator,
          value=numeric,
          unit=unit,
          kind=kind,
          label=labeler(value),
          source_text=match.group(0),
        ))
        return

  def _elements(self, text: str) -> tuple[set[str], set[str]]:
    included: set[str] = set()
    excluded: set[str] = set()
    for name, symbol in _ELEMENT_NAMES.items():
      if not re.search(rf"\b{re.escape(name)}\b", text):
        continue
      if re.search(rf"\b{re.escape(name)}(?:-free|\s+free)|(?:without|exclude|excluding|no)\s+{re.escape(name)}\b", text):
        excluded.add(symbol)
      else:
        included.add(symbol)
    for symbol in {"Al", "Co", "Cu", "Fe", "Li", "Mg", "Mn", "N", "Ni", "O", "S", "Si", "Ti", "V", "W", "Zn", "Zr"}:
      if not re.search(rf"(?<![A-Za-z]){symbol}(?![a-z])", text, flags=re.IGNORECASE if len(symbol) > 1 else 0):
        continue
      free = re.search(rf"(?<![A-Za-z]){symbol}(?:-free|\s+free)(?![A-Za-z])", text, flags=re.IGNORECASE)
      if free:
        excluded.add(symbol)
      elif len(symbol) > 1:
        included.add(symbol)
    return included - excluded, excluded
