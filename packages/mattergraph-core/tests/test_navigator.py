from __future__ import annotations

from copy import deepcopy

from mattergraph.navigator import (
  CandidateStatus,
  Constraint,
  ConstraintKind,
  ConstraintOperator,
  ConstraintPlan,
  DeterministicInterpreter,
  NavigatorEngine,
  NavigatorRecord,
  OutcomeState,
  default_registry,
  freeze_index,
  navigator_record_from_material,
)
from mattergraph.schema.material import Material
from mattergraph.schema.structure import CrystalStructure


def _record(
  identifier: str,
  *,
  formula: str = "TiN",
  elements: list[str] | None = None,
  nsites: int = 2,
  density: float | None = 5.0,
  magnetization: float | None = 0.05,
  force: float | None = 0.1,
) -> NavigatorRecord:
  elements = elements or ["N", "Ti"]
  return NavigatorRecord(
    material_id=identifier,
    formula=formula,
    elements=elements,
    nelements=len(elements),
    nsites=nsites,
    functional="pbe",
    cross_compatibility=True,
    properties={
      "density": density,
      "absolute_total_magnetization": magnetization,
      "absolute_total_magnetization_per_site": (
        magnetization / nsites if magnetization is not None else None
      ),
      "maximum_absolute_reported_site_moment": None,
      "maximum_force_norm": force,
      "signed_total_magnetization": -magnetization if magnetization is not None else None,
      "raw_total_energy": None,
    },
  )


def _plan(*constraints: Constraint) -> ConstraintPlan:
  return ConstraintPlan(
    constraints=list(constraints),
    registry_version="navigator-registry-v1",
    index_id="test-index",
  )


def _constraint(
  identifier: str,
  field: str,
  operator: ConstraintOperator,
  value: float | int | str | bool | list[str],
  kind: ConstraintKind,
  *,
  unit: str | None = None,
  locked: bool = False,
) -> Constraint:
  return Constraint(
    id=identifier,
    field=field,
    operator=operator,
    value=value,
    unit=unit,
    kind=kind,
    confirmed=True,
    locked=locked,
  )


def test_interpreter_compiles_bounded_request_without_claiming_nonmagnetic() -> None:
  registry = default_registry(index_id="test-index")
  result = DeterministicInterpreter(registry).interpret(
    "Find a cobalt-free ternary oxide with fewer than 20 sites and "
    "magnetization below 0.1 μB."
  )

  by_field = {constraint.field: constraint for constraint in result.plan.constraints}
  element_constraints = [
    constraint for constraint in result.plan.constraints if constraint.field == "elements"
  ]
  assert {constraint.operator for constraint in element_constraints} == {
    ConstraintOperator.INCLUDE_ALL,
    ConstraintOperator.EXCLUDE_ANY,
  }
  assert by_field["nelements"].value == 3
  assert by_field["nsites"].operator == ConstraintOperator.LT
  assert by_field["absolute_total_magnetization"].unit == "μB/cell"
  assert all(not constraint.confirmed for constraint in result.plan.constraints)
  assert result.interpreter["model_used"] is False


def test_nonmagnetic_stays_unresolved() -> None:
  result = DeterministicInterpreter(default_registry(index_id="test-index")).interpret(
    "Find a nonmagnetic nitride"
  )
  assert result.plan.unresolved_constraints[0].code == "ambiguous_magnetic_semantics"
  assert not any(
    constraint.field == "absolute_total_magnetization"
    for constraint in result.plan.constraints
  )


def test_validator_separates_conflict_and_capability_mismatch() -> None:
  engine = NavigatorEngine([_record("a")], default_registry(index_id="test-index"))
  conflict = _plan(
    _constraint("a", "elements", ConstraintOperator.INCLUDE_ALL, ["Co"], ConstraintKind.CATEGORICAL),
    _constraint("b", "elements", ConstraintOperator.EXCLUDE_ANY, ["Co"], ConstraintKind.CATEGORICAL),
  )
  capability = _plan(
    _constraint("a", "functional", ConstraintOperator.EQ, "scan", ConstraintKind.CATEGORICAL, locked=True),
  )

  assert engine.evaluate(conflict).state == OutcomeState.PLAN_CONFLICT
  assert engine.evaluate(capability).state == OutcomeState.INDEX_CAPABILITY_MISMATCH


def test_registry_owns_semantic_class_and_numeric_value_type() -> None:
  engine = NavigatorEngine([_record("a")], default_registry(index_id="test-index"))
  wrong_class = _plan(
    _constraint(
      "a",
      "maximum_force_norm",
      ConstraintOperator.LT,
      0.2,
      ConstraintKind.PHYSICAL,
      unit="eV/Å",
    )
  )
  wrong_value = _plan(
    _constraint(
      "a",
      "density",
      ConstraintOperator.LT,
      "dense",
      ConstraintKind.PHYSICAL,
      unit="g/cm^3",
    )
  )

  class_result = engine.validate(wrong_class)
  value_result = engine.validate(wrong_value)
  assert class_result.state == OutcomeState.INDEX_CAPABILITY_MISMATCH
  assert {issue.code for issue in class_result.issues} == {"semantic_class_mismatch"}
  assert value_result.state == OutcomeState.INDEX_CAPABILITY_MISMATCH
  assert "invalid_numeric_value" in {issue.code for issue in value_result.issues}


def test_evaluator_distinguishes_feasible_unknown_and_empty() -> None:
  records = [_record("known", density=5.0), _record("missing", density=None)]
  engine = NavigatorEngine(records, default_registry(index_id="test-index"))
  feasible = _plan(
    _constraint("d", "density", ConstraintOperator.LT, 6.0, ConstraintKind.PHYSICAL, unit="g/cm^3")
  )
  unknown = _plan(
    _constraint("d", "density", ConstraintOperator.LT, 4.0, ConstraintKind.PHYSICAL, unit="g/cm^3")
  )
  empty_engine = NavigatorEngine([records[0]], default_registry(index_id="test-index"))

  assert engine.evaluate(feasible).state == OutcomeState.FEASIBLE_SET
  assert engine.evaluate(unknown).state == OutcomeState.EVIDENCE_UNKNOWN
  empty = empty_engine.evaluate(unknown)
  assert empty.state == OutcomeState.NO_FEASIBLE_SET
  assert empty.candidates[0].status == CandidateStatus.FAIL


def test_physical_and_quality_relaxations_remain_separate() -> None:
  records = [
    _record("physical", density=5.0, force=0.1),
    _record("quality", density=3.0, force=0.4),
  ]
  engine = NavigatorEngine(records, default_registry(index_id="test-index"))
  plan = _plan(
    _constraint("d", "density", ConstraintOperator.LT, 4.0, ConstraintKind.PHYSICAL, unit="g/cm^3"),
    _constraint(
      "f",
      "maximum_force_norm",
      ConstraintOperator.LT,
      0.2,
      ConstraintKind.CALCULATION_QUALITY,
      unit="eV/Å",
    ),
  )

  result = engine.relaxations(plan)
  assert result.state == OutcomeState.NO_FEASIBLE_SET
  assert result.physical_relaxations
  assert result.quality_relaxations
  assert all(
    change.field == "density"
    for path in result.physical_relaxations
    for change in path.changes
  )
  assert all(
    change.field == "maximum_force_norm"
    for path in result.quality_relaxations
    for change in path.changes
  )
  assert "less-converged" in result.quality_relaxations[0].changes[0].message


def test_locked_constraints_are_never_relaxed() -> None:
  engine = NavigatorEngine([_record("a", density=5.0)], default_registry(index_id="test-index"))
  plan = _plan(
    _constraint(
      "d",
      "density",
      ConstraintOperator.LT,
      4.0,
      ConstraintKind.PHYSICAL,
      unit="g/cm^3",
      locked=True,
    )
  )
  assert engine.relaxations(plan).physical_relaxations == []


def test_index_sampling_redistributes_exhausted_strata_deterministically() -> None:
  records = [_raw_record(index, small=index < 1) for index in range(12)]
  first = freeze_index(deepcopy(records), target_count=10)
  second = freeze_index(list(reversed(deepcopy(records))), target_count=10)

  assert len(first.records) == 10
  assert first.manifest["manifest_sha256"] == second.manifest["manifest_sha256"]
  assert first.manifest["selected_ids"] == second.manifest["selected_ids"]
  assert any(item["initial_quota"] > item["population"] for item in first.manifest["strata"].values())
  assert first.manifest["redistributions"]
  assert sum(item["final_quota"] for item in first.manifest["strata"].values()) == 10


def test_raw_arrays_drive_versioned_density_force_and_magnetic_derivations() -> None:
  material = Material(
    material_id="raw-tin",
    source_id="raw-tin",
    formula="TiN",
    structure=CrystalStructure(
      lattice=[[3, 0, 0], [0, 3, 0], [0, 0, 3]],
      species=["Ti", "N"],
      coords=[[0, 0, 0], [0.5, 0.5, 0.5]],
    ),
  )
  record = navigator_record_from_material(
    material,
    raw_record={
      "total_magnetization": -0.4,
      "magnetic_moments": [0.7, -0.3],
      "forces": [[3.0, 4.0, 0.0], [0.0, 0.0, 0.0]],
    },
  )

  assert record.properties["absolute_total_magnetization"] == 0.4
  assert record.properties["absolute_total_magnetization_per_site"] == 0.2
  assert record.properties["maximum_absolute_reported_site_moment"] == 0.7
  assert record.properties["maximum_force_norm"] == 5.0
  assert 3.7 < float(record.properties["density"]) < 3.9
  assert record.property_provenance["density"]["atomic_mass_table"] == (
    "mattergraph-atomic-masses-v1"
  )
  assert record.property_provenance["maximum_force_norm"]["input_sha256"]
  assert record.property_provenance["maximum_force_norm"]["status"] == "available"


def test_invalid_raw_arrays_become_missing_evidence_with_failure_provenance() -> None:
  material = Material(
    material_id="raw-tin",
    formula="TiN",
    structure=CrystalStructure(
      lattice=[[3, 0, 0], [0, 3, 0], [0, 0, 3]],
      species=["Ti", "N"],
      coords=[[0, 0, 0], [0.5, 0.5, 0.5]],
    ),
  )
  record = navigator_record_from_material(
    material,
    raw_record={"magnetic_moments": [0.2], "forces": [[0.0, 0.0, 0.0]]},
  )

  assert record.properties["maximum_absolute_reported_site_moment"] is None
  assert record.properties["maximum_force_norm"] is None
  assert "site count" in record.property_provenance[
    "maximum_absolute_reported_site_moment"
  ]["failure_reason"]
  assert "matching the site count" in record.property_provenance[
    "maximum_force_norm"
  ]["failure_reason"]


def _raw_record(index: int, *, small: bool) -> dict[str, object]:
  nsites = 2 if small else 10
  return {
    "immutable_id": f"src{index:03d}",
    "formula": "TiN",
    "functional": "pbe",
    "cross_compatibility": True,
    "nperiodic_dimensions": 3,
    "nelements": 2 if small else 4,
    "nsites": nsites,
    "lattice_vectors": [[3, 0, 0], [0, 3, 0], [0, 0, 3]],
    "species_at_sites": ["Ti"] * nsites,
    "cartesian_site_positions": [[0, 0, 0]] * nsites,
    "total_magnetization": 0.0 if small else None,
    "forces": [[0, 0, 0]] * nsites,
  }
