from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class AseJobSpec(BaseModel):
  engine: str = "ase"
  calc_name: str = "emt"  # emt, lj (extend with GPAW/others locally)
  fmax: float = 0.05
  max_steps: int = 200
  n_cores: int = 1


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
  log: str | None = None
