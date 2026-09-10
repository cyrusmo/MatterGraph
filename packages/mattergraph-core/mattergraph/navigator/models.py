from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mattergraph.schema.structure import CrystalStructure


ConstraintValue = float | int | str | bool | list[str]


class ConstraintKind(str, Enum):
  PHYSICAL = "physical"
  CATEGORICAL = "categorical"
  CALCULATION_QUALITY = "calculation_quality"
  EVIDENCE = "evidence"


class ConstraintOperator(str, Enum):
  EQ = "eq"
  LT = "lt"
  LTE = "lte"
  GT = "gt"
  GTE = "gte"
  INCLUDE_ALL = "include_all"
  EXCLUDE_ANY = "exclude_any"


class OutcomeState(str, Enum):
  FEASIBLE_SET = "feasible_set"
  PLAN_CONFLICT = "plan_conflict"
  INDEX_CAPABILITY_MISMATCH = "index_capability_mismatch"
  EVIDENCE_UNKNOWN = "evidence_unknown"
  NO_FEASIBLE_SET = "no_feasible_set"


class CandidateStatus(str, Enum):
  PASS = "pass"
  FAIL = "fail"
  UNKNOWN = "unknown"


class Constraint(BaseModel):
  model_config = ConfigDict(extra="forbid", validate_assignment=True)

  id: str
  field: str
  operator: ConstraintOperator
  value: ConstraintValue
  unit: str | None = None
  kind: ConstraintKind
  locked: bool = False
  confirmed: bool = False
  label: str | None = None
  source_text: str | None = None

  @field_validator("id", "field")
  @classmethod
  def _nonempty(cls, value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
      raise ValueError("constraint id and field must not be empty")
    return cleaned


class UnresolvedConstraint(BaseModel):
  model_config = ConfigDict(extra="forbid")

  id: str
  text: str
  reason: str
  code: str
  actions: list[str] = Field(default_factory=list)


class ConstraintPlan(BaseModel):
  model_config = ConfigDict(extra="forbid", validate_assignment=True)

  constraints: list[Constraint] = Field(default_factory=list)
  unresolved_constraints: list[UnresolvedConstraint] = Field(default_factory=list)
  registry_version: str
  index_id: str
  engine_version: str = "navigator-engine-v1"
  interpreter_version: str | None = None

  @model_validator(mode="after")
  def _unique_ids(self) -> ConstraintPlan:
    identifiers = [constraint.id for constraint in self.constraints]
    identifiers.extend(item.id for item in self.unresolved_constraints)
    if len(identifiers) != len(set(identifiers)):
      raise ValueError("constraint and unresolved identifiers must be unique")
    return self


class RegistryEntry(BaseModel):
  model_config = ConfigDict(extra="forbid")

  field: str
  label: str
  kind: ConstraintKind
  executable: bool
  unit: str | None
  operators: list[ConstraintOperator]
  source: str
  derivation_id: str | None = None
  comparability_scope: str
  missingness: str
  relaxable: bool
  confirmation_required: bool = False
  display_only: bool = False
  bounds: tuple[float, float] | None = None
  supported_values: list[str] | None = None
  scientific_note: str | None = None


class PropertyRegistry(BaseModel):
  model_config = ConfigDict(extra="forbid")

  version: str
  index_id: str
  entries: list[RegistryEntry]
  digest: str

  def entry_map(self) -> dict[str, RegistryEntry]:
    return {entry.field: entry for entry in self.entries}


class ValidationIssue(BaseModel):
  model_config = ConfigDict(extra="forbid")

  code: str
  message: str
  constraint_ids: list[str] = Field(default_factory=list)
  field: str | None = None


class PlanValidationResult(BaseModel):
  model_config = ConfigDict(extra="forbid")

  valid: bool
  state: OutcomeState | None = None
  issues: list[ValidationIssue] = Field(default_factory=list)


class ConstraintCheck(BaseModel):
  model_config = ConfigDict(extra="forbid")

  constraint_id: str
  status: CandidateStatus
  actual: ConstraintValue | None = None
  expected: ConstraintValue
  unit: str | None = None
  message: str


class NavigatorStructure(BaseModel):
  model_config = ConfigDict(extra="forbid")

  structure_id: str
  source_id: str
  source: str
  method: str
  structure: CrystalStructure
  lattice_unit: Literal["angstrom"] = "angstrom"
  coordinate_convention: Literal["fractional"] = "fractional"
  occupancy_convention: Literal["species_mapping"] = "species_mapping"
  periodic_axes: tuple[bool, bool, bool] = (True, True, True)
  provenance: list[dict[str, Any]] = Field(default_factory=list)


class NavigatorRecord(BaseModel):
  model_config = ConfigDict(extra="forbid")

  material_id: str
  formula: str
  elements: list[str]
  nelements: int
  nsites: int
  functional: str
  cross_compatibility: bool
  properties: dict[str, float | int | str | bool | None] = Field(default_factory=dict)
  property_provenance: dict[str, dict[str, Any]] = Field(default_factory=dict)
  structure: NavigatorStructure | None = None


class CandidateEvaluation(BaseModel):
  model_config = ConfigDict(extra="forbid")

  material_id: str
  formula: str
  status: CandidateStatus
  checks: list[ConstraintCheck]
  properties: dict[str, float | int | str | bool | None]


class EvaluationResult(BaseModel):
  model_config = ConfigDict(extra="forbid")

  state: OutcomeState
  index_id: str
  registry_version: str
  engine_version: str
  total_count: int
  feasible_count: int
  indeterminate_count: int
  candidates: list[CandidateEvaluation] = Field(default_factory=list)
  issues: list[ValidationIssue] = Field(default_factory=list)
  scientific_boundary: str = (
    "Eligibility and recovery are deterministic and relative to the frozen index; "
    "they are not causal claims about material performance."
  )


class ConstraintChange(BaseModel):
  model_config = ConfigDict(extra="forbid")

  constraint_id: str
  field: str
  old_operator: ConstraintOperator
  old_value: ConstraintValue
  new_operator: ConstraintOperator
  new_value: ConstraintValue
  unit: str | None
  normalized_change: float
  message: str


class RelaxationPath(BaseModel):
  model_config = ConfigDict(extra="forbid")

  path_id: str
  changes: list[ConstraintChange]
  recovered_count: int
  recovered_material_ids: list[str]
  maximum_normalized_change: float
  total_normalized_change: float
  relative_to: str
  causal: Literal[False] = False


class RecoveryAction(BaseModel):
  model_config = ConfigDict(extra="forbid")

  code: str
  label: str
  detail: str


class RelaxationResult(BaseModel):
  model_config = ConfigDict(extra="forbid")

  state: OutcomeState
  physical_relaxations: list[RelaxationPath] = Field(default_factory=list)
  quality_relaxations: list[RelaxationPath] = Field(default_factory=list)
  evidence_recoveries: list[RecoveryAction] = Field(default_factory=list)
  capability_recoveries: list[RecoveryAction] = Field(default_factory=list)
  scientific_boundary: str


class InterpretationResult(BaseModel):
  model_config = ConfigDict(extra="forbid")

  plan: ConstraintPlan
  interpreter: dict[str, Any]
  confirmation_required: bool
  privacy: str = "Raw prompt and provider output are not persisted by MatterGraph."
