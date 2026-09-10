from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Iterable

from mattergraph.navigator.models import (
  CandidateEvaluation,
  CandidateStatus,
  Constraint,
  ConstraintChange,
  ConstraintCheck,
  ConstraintKind,
  ConstraintOperator,
  ConstraintPlan,
  EvaluationResult,
  NavigatorRecord,
  OutcomeState,
  PlanValidationResult,
  PropertyRegistry,
  RecoveryAction,
  RelaxationPath,
  RelaxationResult,
)
from mattergraph.navigator.registry import canonical_json
from mattergraph.navigator.validation import validate_plan


class NavigatorEngine:
  """Deterministic executor and counterfactual recovery engine for a frozen index."""

  version = "navigator-engine-v1"

  def __init__(self, records: Iterable[NavigatorRecord], registry: PropertyRegistry) -> None:
    self.records = list(records)
    self.registry = registry
    self.entries = registry.entry_map()

  def validate(self, plan: ConstraintPlan) -> PlanValidationResult:
    return validate_plan(plan, self.registry)

  def evaluate(self, plan: ConstraintPlan) -> EvaluationResult:
    validation = self.validate(plan)
    if not validation.valid:
      return EvaluationResult(
        state=validation.state or OutcomeState.INDEX_CAPABILITY_MISMATCH,
        index_id=self.registry.index_id,
        registry_version=self.registry.version,
        engine_version=self.version,
        total_count=len(self.records),
        feasible_count=0,
        indeterminate_count=0,
        issues=validation.issues,
      )

    candidates = [self._evaluate_record(record, plan.constraints) for record in self.records]
    feasible_count = sum(item.status == CandidateStatus.PASS for item in candidates)
    indeterminate_count = sum(item.status == CandidateStatus.UNKNOWN for item in candidates)
    if feasible_count:
      state = OutcomeState.FEASIBLE_SET
    elif indeterminate_count:
      state = OutcomeState.EVIDENCE_UNKNOWN
    else:
      state = OutcomeState.NO_FEASIBLE_SET
    return EvaluationResult(
      state=state,
      index_id=self.registry.index_id,
      registry_version=self.registry.version,
      engine_version=self.version,
      total_count=len(self.records),
      feasible_count=feasible_count,
      indeterminate_count=indeterminate_count,
      candidates=candidates,
    )

  def relaxations(self, plan: ConstraintPlan) -> RelaxationResult:
    evaluation = self.evaluate(plan)
    boundary = (
      f"All recovery paths are deterministic and relative to {self.registry.index_id}; "
      "they do not predict that changing a requirement causes material performance."
    )
    if evaluation.state == OutcomeState.PLAN_CONFLICT:
      return RelaxationResult(state=evaluation.state, scientific_boundary=boundary)
    if evaluation.state == OutcomeState.INDEX_CAPABILITY_MISMATCH:
      return RelaxationResult(
        state=evaluation.state,
        capability_recoveries=[
          RecoveryAction(
            code="keep_unevaluated",
            label="Keep as unevaluated",
            detail="Preserve the requirement without fabricating an executable filter.",
          ),
          RecoveryAction(
            code="remove_after_confirmation",
            label="Remove from execution",
            detail="Remove the unsupported requirement only after explicit confirmation.",
          ),
          RecoveryAction(
            code="export_data_request",
            label="Export data request",
            detail="Record the requirement as a follow-up dataset or test need.",
          ),
        ],
        scientific_boundary=boundary,
      )
    if evaluation.state == OutcomeState.EVIDENCE_UNKNOWN:
      unknown_fields = sorted({
        check.constraint_id
        for candidate in evaluation.candidates
        for check in candidate.checks
        if check.status == CandidateStatus.UNKNOWN
      })
      return RelaxationResult(
        state=evaluation.state,
        evidence_recoveries=[
          RecoveryAction(
            code="require_reported_evidence",
            label="Require reported evidence",
            detail=f"Restrict results to records reporting: {', '.join(unknown_fields)}.",
          ),
          RecoveryAction(
            code="keep_unevaluated",
            label="Keep requirement unevaluated",
            detail="Preserve missingness and export candidates as indeterminate.",
          ),
          RecoveryAction(
            code="export_follow_up",
            label="Export follow-up test",
            detail="Create a bounded measurement or data-acquisition request.",
          ),
        ],
        scientific_boundary=boundary,
      )
    if evaluation.state != OutcomeState.NO_FEASIBLE_SET:
      return RelaxationResult(state=evaluation.state, scientific_boundary=boundary)
    return RelaxationResult(
      state=evaluation.state,
      physical_relaxations=self._frontier(
        plan,
        {ConstraintKind.PHYSICAL, ConstraintKind.CATEGORICAL},
      ),
      quality_relaxations=self._frontier(plan, {ConstraintKind.CALCULATION_QUALITY}),
      scientific_boundary=boundary,
    )

  def _evaluate_record(
    self,
    record: NavigatorRecord,
    constraints: list[Constraint],
  ) -> CandidateEvaluation:
    checks = [self._check(record, constraint) for constraint in constraints]
    if any(check.status == CandidateStatus.FAIL for check in checks):
      status = CandidateStatus.FAIL
    elif any(check.status == CandidateStatus.UNKNOWN for check in checks):
      status = CandidateStatus.UNKNOWN
    else:
      status = CandidateStatus.PASS
    properties = {
      "nelements": record.nelements,
      "nsites": record.nsites,
      "functional": record.functional,
      "cross_compatibility": record.cross_compatibility,
      **record.properties,
    }
    return CandidateEvaluation(
      material_id=record.material_id,
      formula=record.formula,
      status=status,
      checks=checks,
      properties=properties,
    )

  def _check(self, record: NavigatorRecord, constraint: Constraint) -> ConstraintCheck:
    actual = _record_value(record, constraint.field)
    if actual is None:
      return ConstraintCheck(
        constraint_id=constraint.id,
        status=CandidateStatus.UNKNOWN,
        expected=constraint.value,
        unit=constraint.unit,
        message=f"{constraint.field} is not reported or derivable for this indexed record.",
      )
    passed = _compare(actual, constraint.operator, constraint.value)
    return ConstraintCheck(
      constraint_id=constraint.id,
      status=CandidateStatus.PASS if passed else CandidateStatus.FAIL,
      actual=actual,
      expected=constraint.value,
      unit=constraint.unit,
      message=_check_message(constraint, actual, passed),
    )

  def _frontier(
    self,
    plan: ConstraintPlan,
    relax_kinds: set[ConstraintKind],
  ) -> list[RelaxationPath]:
    relaxable_ids = [
      constraint.id
      for constraint in plan.constraints
      if constraint.kind in relax_kinds
      and not constraint.locked
      and self.entries[constraint.field].relaxable
    ]
    if not relaxable_ids:
      return []
    candidates: list[tuple[dict[str, float], list[ConstraintChange]]] = []
    for record in self.records:
      checks = {item.constraint_id: item for item in self._evaluate_record(record, plan.constraints).checks}
      changes: list[ConstraintChange] = []
      blocked = False
      for constraint in plan.constraints:
        check = checks[constraint.id]
        if check.status == CandidateStatus.PASS:
          continue
        can_change = (
          check.status == CandidateStatus.FAIL
          and constraint.kind in relax_kinds
          and not constraint.locked
          and self.entries[constraint.field].relaxable
        )
        if not can_change:
          blocked = True
          break
        change = self._minimal_change(constraint, check.actual)
        if change is None:
          blocked = True
          break
        changes.append(change)
      if blocked or not changes:
        continue
      vector = {identifier: 0.0 for identifier in relaxable_ids}
      for change in changes:
        vector[change.constraint_id] = change.normalized_change
      candidates.append((vector, changes))

    grouped: dict[str, tuple[dict[str, float], list[ConstraintChange]]] = {}
    for vector, changes in candidates:
      body = [change.model_dump(mode="json") for change in changes]
      digest = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
      grouped.setdefault(digest, (vector, changes))
    nondominated = _pareto_frontier(list(grouped.values()))

    paths: list[RelaxationPath] = []
    for vector, changes in nondominated:
      body = [change.model_dump(mode="json") for change in changes]
      digest = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
      changed_plan = deepcopy(plan)
      by_id = {change.constraint_id: change for change in changes}
      for constraint in changed_plan.constraints:
        if constraint.id in by_id:
          change = by_id[constraint.id]
          constraint.operator = change.new_operator
          constraint.value = change.new_value
      recovered = self.evaluate(changed_plan)
      recovered_ids = sorted(
        candidate.material_id
        for candidate in recovered.candidates
        if candidate.status == CandidateStatus.PASS
      )
      nonzero = [value for value in vector.values() if value > 0]
      paths.append(
        RelaxationPath(
          path_id=digest[:16],
          changes=changes,
          recovered_count=len(recovered_ids),
          recovered_material_ids=recovered_ids,
          maximum_normalized_change=max(nonzero, default=0.0),
          total_normalized_change=sum(nonzero),
          relative_to=self.registry.index_id,
        )
      )
    paths.sort(
      key=lambda path: (
        len(path.changes),
        path.maximum_normalized_change,
        path.total_normalized_change,
        path.path_id,
      )
    )
    return paths[:8]

  def _minimal_change(
    self,
    constraint: Constraint,
    actual: object,
  ) -> ConstraintChange | None:
    entry = self.entries[constraint.field]
    new_operator = constraint.operator
    new_value: object = actual
    if constraint.operator == ConstraintOperator.LT:
      new_operator = ConstraintOperator.LTE
    elif constraint.operator == ConstraintOperator.GT:
      new_operator = ConstraintOperator.GTE
    elif constraint.operator == ConstraintOperator.INCLUDE_ALL:
      required = {str(value) for value in _as_list(constraint.value)}
      present = {str(value) for value in _as_list(actual)}
      new_value = sorted(required & present)
    elif constraint.operator == ConstraintOperator.EXCLUDE_ANY:
      excluded = {str(value) for value in _as_list(constraint.value)}
      present = {str(value) for value in _as_list(actual)}
      new_value = sorted(excluded - present)
    numeric_change = _normalized_change(constraint.value, new_value, entry.bounds)
    return ConstraintChange(
      constraint_id=constraint.id,
      field=constraint.field,
      old_operator=constraint.operator,
      old_value=constraint.value,
      new_operator=new_operator,
      new_value=new_value,  # type: ignore[arg-type]
      unit=constraint.unit,
      normalized_change=numeric_change,
      message=_change_message(constraint, new_operator, new_value),
    )


def _record_value(record: NavigatorRecord, field: str) -> object:
  if field == "formula":
    return record.formula
  if field == "elements":
    return record.elements
  if field == "nelements":
    return record.nelements
  if field == "nsites":
    return record.nsites
  if field == "functional":
    return record.functional
  if field == "cross_compatibility":
    return record.cross_compatibility
  return record.properties.get(field)


def _compare(actual: object, operator: ConstraintOperator, expected: object) -> bool:
  if operator == ConstraintOperator.INCLUDE_ALL:
    return set(_as_list(expected)) <= set(_as_list(actual))
  if operator == ConstraintOperator.EXCLUDE_ANY:
    return not bool(set(_as_list(expected)) & set(_as_list(actual)))
  if operator == ConstraintOperator.EQ:
    if isinstance(actual, str) and isinstance(expected, str):
      return actual.lower() == expected.lower()
    return actual == expected
  if not isinstance(actual, (int, float)) or not isinstance(expected, (int, float)):
    return False
  if operator == ConstraintOperator.LT:
    return float(actual) < float(expected)
  if operator == ConstraintOperator.LTE:
    return float(actual) <= float(expected)
  if operator == ConstraintOperator.GT:
    return float(actual) > float(expected)
  if operator == ConstraintOperator.GTE:
    return float(actual) >= float(expected)
  return False


def _as_list(value: object) -> list[object]:
  return list(value) if isinstance(value, (list, tuple, set)) else [value]


def _normalized_change(old: object, new: object, bounds: tuple[float, float] | None) -> float:
  if isinstance(old, (int, float)) and isinstance(new, (int, float)) and bounds:
    width = max(bounds[1] - bounds[0], 1e-12)
    return abs(float(new) - float(old)) / width
  old_set = set(_as_list(old))
  new_set = set(_as_list(new))
  return float(len(old_set.symmetric_difference(new_set)) or 1)


def _dominates(left: dict[str, float], right: dict[str, float]) -> bool:
  keys = set(left) | set(right)
  no_worse = all(left.get(key, 0.0) <= right.get(key, 0.0) for key in keys)
  strictly_better = any(left.get(key, 0.0) < right.get(key, 0.0) for key in keys)
  return no_worse and strictly_better


def _pareto_frontier(
  candidates: list[tuple[dict[str, float], list[ConstraintChange]]],
) -> list[tuple[dict[str, float], list[ConstraintChange]]]:
  """Maintain a skyline incrementally so 25k records do not allocate an N×N matrix."""
  ordered = sorted(
    candidates,
    key=lambda item: (
      sum(value > 0 for value in item[0].values()),
      max(item[0].values(), default=0.0),
      sum(item[0].values()),
      tuple(sorted(item[0].items())),
    ),
  )
  frontier: list[tuple[dict[str, float], list[ConstraintChange]]] = []
  for candidate in ordered:
    if any(_dominates(existing[0], candidate[0]) for existing in frontier):
      continue
    frontier = [
      existing for existing in frontier if not _dominates(candidate[0], existing[0])
    ]
    frontier.append(candidate)
  return frontier


def _check_message(constraint: Constraint, actual: object, passed: bool) -> str:
  state = "satisfies" if passed else "fails"
  unit = f" {constraint.unit}" if constraint.unit else ""
  return (
    f"{constraint.field}={actual}{unit} {state} "
    f"{constraint.operator.value} {constraint.value}{unit}."
  )


def _change_message(
  constraint: Constraint,
  operator: ConstraintOperator,
  value: object,
) -> str:
  unit = f" {constraint.unit}" if constraint.unit else ""
  prefix = (
    "Admit less-converged calculations by changing"
    if constraint.kind == ConstraintKind.CALCULATION_QUALITY
    else "Change"
  )
  return (
    f"{prefix} {constraint.field} from {constraint.operator.value} {constraint.value}{unit} "
    f"to {operator.value} {value}{unit}."
  )
