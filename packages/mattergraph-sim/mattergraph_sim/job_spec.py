from __future__ import annotations

import uuid
from typing import Any, Literal

from mattergraph.schema.structure import CrystalStructure
from pydantic import BaseModel, Field, field_validator

_SUPPORTED_ASE_CALCULATORS = {"emt"}


class AseJobSpec(BaseModel):
  engine: Literal["ase"] = "ase"
  calc_name: str = "emt"
  fmax: float = 0.05
  max_steps: int = 200
  n_cores: int = 1

  @field_validator("calc_name")
  @classmethod
  def _normalize_calc_name(cls, value: str) -> str:
    calc_name = value.strip().lower()
    if calc_name not in _SUPPORTED_ASE_CALCULATORS:
      supported = ", ".join(sorted(_SUPPORTED_ASE_CALCULATORS))
      msg = f"unsupported ASE calculator {calc_name!r}; supported calculators: {supported}"
      raise ValueError(msg)
    return calc_name

  @field_validator("fmax")
  @classmethod
  def _positive_fmax(cls, value: float) -> float:
    if value <= 0:
      msg = "fmax must be positive"
      raise ValueError(msg)
    return value

  @field_validator("max_steps", "n_cores")
  @classmethod
  def _positive_ints(cls, value: int, info: Any) -> int:
    if value < 1:
      msg = f"{info.field_name} must be at least 1"
      raise ValueError(msg)
    return value


class SimulationResult(BaseModel):
  engine: str
  calculator: str
  converged: bool | None = None
  steps: int | None = None
  energy: float | None = None
  max_force: float | None = None
  relaxed_structure: CrystalStructure | None = None


class SimulationJob(BaseModel):
  job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
  spec: AseJobSpec
  input_structure: dict[str, Any] = Field(
    default_factory=dict,
    description="Serialized :class:`CrystalStructure` or pymatgen dict",
  )
  kind: Literal["relax", "sc", "md"] = "relax"
  status: Literal["pending", "running", "completed", "failed"] = "pending"
  result_uri: str | None = None
  result: SimulationResult | None = None
  error: str | None = None
  log: str | None = None
