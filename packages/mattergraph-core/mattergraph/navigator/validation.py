from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from pymatgen.core import Composition

from mattergraph.navigator.models import (
  Constraint,
  ConstraintOperator,
  ConstraintPlan,
  OutcomeState,
  PlanValidationResult,
  PropertyRegistry,
  ValidationIssue,
)


def validate_plan(plan: ConstraintPlan, registry: PropertyRegistry) -> PlanValidationResult:
  conflicts: list[ValidationIssue] = []
  capabilities: list[ValidationIssue] = []
  entries = registry.entry_map()

  if plan.registry_version != registry.version or plan.index_id != registry.index_id:
    capabilities.append(
      ValidationIssue(
        code="version_mismatch",
        message="The confirmed plan targets a different registry or frozen index.",
      )
    )

  for unresolved in plan.unresolved_constraints:
    capabilities.append(
      ValidationIssue(
        code=unresolved.code,
        message=unresolved.reason,
        constraint_ids=[unresolved.id],
      )
    )

  for constraint in plan.constraints:
    entry = entries.get(constraint.field)
    if entry is None:
      capabilities.append(
        ValidationIssue(
          code="unsupported_field",
          message=f"{constraint.field!r} is not in the frozen property registry.",
          constraint_ids=[constraint.id],
          field=constraint.field,
        )
      )
      continue
    if not entry.executable:
      capabilities.append(
        ValidationIssue(
          code="field_not_executable",
          message=f"{entry.label} is {entry.comparability_scope}.",
          constraint_ids=[constraint.id],
          field=constraint.field,
        )
      )
    if constraint.kind != entry.kind:
      capabilities.append(
        ValidationIssue(
          code="semantic_class_mismatch",
          message=(
            f"{entry.label} is registry-owned semantic class {entry.kind.value}, not "
            f"{constraint.kind.value}."
          ),
          constraint_ids=[constraint.id],
          field=constraint.field,
        )
      )
    if constraint.operator not in entry.operators:
      capabilities.append(
        ValidationIssue(
          code="unsupported_operator",
          message=f"{constraint.operator.value} is not supported for {entry.label}.",
          constraint_ids=[constraint.id],
          field=constraint.field,
        )
      )
    if entry.bounds is not None and constraint.operator in {
      ConstraintOperator.EQ,
      ConstraintOperator.LT,
      ConstraintOperator.LTE,
      ConstraintOperator.GT,
      ConstraintOperator.GTE,
    } and (
      not isinstance(constraint.value, (int, float))
      or isinstance(constraint.value, bool)
      or not math.isfinite(float(constraint.value))
    ):
      capabilities.append(
        ValidationIssue(
          code="invalid_numeric_value",
          message=f"{entry.label} requires a finite numeric threshold.",
          constraint_ids=[constraint.id],
          field=constraint.field,
        )
      )
    if not constraint.confirmed:
      capabilities.append(
        ValidationIssue(
          code="confirmation_required",
          message=f"Confirm the interpretation of {entry.label} before execution.",
          constraint_ids=[constraint.id],
          field=constraint.field,
        )
      )
    if entry.unit and normalize_unit(constraint.unit) != normalize_unit(entry.unit):
      capabilities.append(
        ValidationIssue(
          code="incompatible_unit",
          message=f"{entry.label} requires {entry.unit}; received {constraint.unit or 'no unit'}.",
          constraint_ids=[constraint.id],
          field=constraint.field,
        )
      )
    if not entry.unit and constraint.unit:
      capabilities.append(
        ValidationIssue(
          code="dimensionally_incompatible_unit",
          message=f"{entry.label} does not accept a physical unit.",
          constraint_ids=[constraint.id],
          field=constraint.field,
        )
      )
    if entry.supported_values is not None:
      supported = {value.lower() for value in entry.supported_values}
      value = str(constraint.value).lower()
      if value not in supported:
        capabilities.append(
          ValidationIssue(
            code="unsupported_index_value",
            message=(
              f"{entry.label}={constraint.value!r} is valid in principle but outside "
              f"{registry.index_id}; supported: {', '.join(entry.supported_values)}."
            ),
            constraint_ids=[constraint.id],
            field=constraint.field,
          )
        )

  conflicts.extend(_element_conflicts(plan.constraints))
  conflicts.extend(_numeric_conflicts(plan.constraints))
  conflicts.extend(_formula_conflicts(plan.constraints))

  if conflicts:
    return PlanValidationResult(
      valid=False,
      state=OutcomeState.PLAN_CONFLICT,
      issues=_dedupe_issues(conflicts),
    )
  if capabilities:
    return PlanValidationResult(
      valid=False,
      state=OutcomeState.INDEX_CAPABILITY_MISMATCH,
      issues=_dedupe_issues(capabilities),
    )
  return PlanValidationResult(valid=True)


def normalize_unit(unit: str | None) -> str | None:
  if unit is None:
    return None
  compact = unit.strip().lower().replace(" ", "").replace("³", "^3")
  aliases = {
    "count": "count",
    "g/cm3": "g/cm^3",
    "g/cm^3": "g/cm^3",
    "μb": "μb/cell",
    "ub": "μb/cell",
    "μb/cell": "μb/cell",
    "ub/cell": "μb/cell",
    "μb/site": "μb/site",
    "ub/site": "μb/site",
    "ev/a": "ev/å",
    "ev/angstrom": "ev/å",
    "ev/å": "ev/å",
  }
  return aliases.get(compact, compact)


def _element_conflicts(constraints: list[Constraint]) -> list[ValidationIssue]:
  included: dict[str, list[str]] = defaultdict(list)
  excluded: dict[str, list[str]] = defaultdict(list)
  for constraint in constraints:
    if constraint.field != "elements" or not isinstance(constraint.value, list):
      continue
    target = included if constraint.operator == ConstraintOperator.INCLUDE_ALL else excluded
    for element in constraint.value:
      target[str(element)].append(constraint.id)
  issues: list[ValidationIssue] = []
  for element in sorted(set(included) & set(excluded)):
    issues.append(
      ValidationIssue(
        code="include_exclude_overlap",
        message=f"{element} is both required and excluded.",
        constraint_ids=sorted(included[element] + excluded[element]),
        field="elements",
      )
    )
  exact_nelements = _exact_numeric(constraints, "nelements")
  if exact_nelements is not None and len(included) > exact_nelements[0]:
    issues.append(
      ValidationIssue(
        code="required_elements_exceed_count",
        message=(
          f"{len(included)} distinct required elements exceed the exact element count "
          f"of {exact_nelements[0]}."
        ),
        constraint_ids=sorted([*sum(included.values(), []), exact_nelements[1]]),
        field="nelements",
      )
    )
  return issues


def _numeric_conflicts(constraints: list[Constraint]) -> list[ValidationIssue]:
  grouped: dict[str, list[Constraint]] = defaultdict(list)
  for constraint in constraints:
    if isinstance(constraint.value, (int, float)) and not isinstance(constraint.value, bool):
      grouped[constraint.field].append(constraint)
  issues: list[ValidationIssue] = []
  for field, items in grouped.items():
    exact = [item for item in items if item.operator == ConstraintOperator.EQ]
    exact_values = {float(item.value) for item in exact}
    if len(exact_values) > 1:
      issues.append(
        ValidationIssue(
          code="conflicting_exact_values",
          message=f"{field} has incompatible exact values.",
          constraint_ids=[item.id for item in exact],
          field=field,
        )
      )
      continue
    lower = -math.inf
    lower_strict = False
    upper = math.inf
    upper_strict = False
    for item in items:
      value = float(item.value)
      if item.operator in {ConstraintOperator.GT, ConstraintOperator.GTE}:
        if value > lower or (value == lower and item.operator == ConstraintOperator.GT):
          lower = value
          lower_strict = item.operator == ConstraintOperator.GT
      if item.operator in {ConstraintOperator.LT, ConstraintOperator.LTE}:
        if value < upper or (value == upper and item.operator == ConstraintOperator.LT):
          upper = value
          upper_strict = item.operator == ConstraintOperator.LT
    if exact_values:
      value = next(iter(exact_values))
      if value < lower or value > upper or (value == lower and lower_strict) or (
        value == upper and upper_strict
      ):
        issues.append(
          ValidationIssue(
            code="exact_outside_range",
            message=f"The exact {field} value contradicts its confirmed range.",
            constraint_ids=[item.id for item in items],
            field=field,
          )
        )
    elif lower > upper or (lower == upper and (lower_strict or upper_strict)):
      issues.append(
        ValidationIssue(
          code="empty_numeric_interval",
          message=f"The confirmed {field} bounds do not overlap.",
          constraint_ids=[item.id for item in items],
          field=field,
        )
      )
  return issues


def _formula_conflicts(constraints: list[Constraint]) -> list[ValidationIssue]:
  formulas = [
    item for item in constraints
    if item.field == "formula" and item.operator == ConstraintOperator.EQ
  ]
  if not formulas:
    return []
  normalized: dict[str, list[str]] = defaultdict(list)
  formula_elements: set[str] = set()
  try:
    for item in formulas:
      reduced = Composition(str(item.value)).reduced_formula
      normalized[reduced].append(item.id)
    formula_elements = {str(element) for element in Composition(str(formulas[0].value)).elements}
  except ValueError:
    return [
      ValidationIssue(
        code="invalid_formula",
        message="A confirmed formula cannot be parsed.",
        constraint_ids=[item.id for item in formulas],
        field="formula",
      )
    ]
  issues: list[ValidationIssue] = []
  if len(normalized) > 1:
    issues.append(
      ValidationIssue(
        code="conflicting_formulas",
        message="The plan requires more than one exact formula.",
        constraint_ids=[item.id for item in formulas],
        field="formula",
      )
    )
  for item in constraints:
    if item.field == "elements" and isinstance(item.value, list):
      values = {str(value) for value in item.value}
      conflict = (
        values - formula_elements
        if item.operator == ConstraintOperator.INCLUDE_ALL
        else values & formula_elements
      )
      if conflict:
        issues.append(
          ValidationIssue(
            code="formula_element_conflict",
            message=(
              f"Formula {formulas[0].value} conflicts with element constraint "
              f"{', '.join(sorted(conflict))}."
            ),
            constraint_ids=[formulas[0].id, item.id],
            field="formula",
          )
        )
  exact_nelements = _exact_numeric(constraints, "nelements")
  if exact_nelements and exact_nelements[0] != len(formula_elements):
    issues.append(
      ValidationIssue(
        code="formula_count_conflict",
        message=(
          f"Formula {formulas[0].value} has {len(formula_elements)} elements, not "
          f"{exact_nelements[0]}."
        ),
        constraint_ids=[formulas[0].id, exact_nelements[1]],
        field="nelements",
      )
    )
  return issues


def _exact_numeric(constraints: list[Constraint], field: str) -> tuple[int, str] | None:
  for item in constraints:
    if item.field == field and item.operator == ConstraintOperator.EQ:
      try:
        return int(item.value), item.id
      except (TypeError, ValueError):
        return None
  return None


def _dedupe_issues(issues: list[ValidationIssue]) -> list[ValidationIssue]:
  seen: set[tuple[Any, ...]] = set()
  out: list[ValidationIssue] = []
  for issue in issues:
    key = (issue.code, issue.field, tuple(sorted(issue.constraint_ids)), issue.message)
    if key not in seen:
      seen.add(key)
      out.append(issue)
  return out
