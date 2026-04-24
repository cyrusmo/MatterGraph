from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SimulationJobRef(BaseModel):
  """Reference to a simulation that produced or post-processes a material result."""

  job_id: str
  engine: Literal["ase", "lammps", "qe", "custom"] = Field(
    default="ase",
    description="ase, lammps, qe, custom",
  )
  spec_version: str = "0.1.0"
  input_uri: str | None = None
  output_uri: str | None = None
  status: Literal["pending", "running", "completed", "failed"] = "pending"

  @field_validator("job_id")
  @classmethod
  def _non_empty_job_id(cls, value: str) -> str:
    out = value.strip()
    if not out:
      msg = "job_id must not be empty"
      raise ValueError(msg)
    return out
