from pydantic import BaseModel, Field


class SimulationJobRef(BaseModel):
  """Reference to a simulation that produced or post-processes a material result."""

  job_id: str
  engine: str = Field(
    default="ase",
    description="ase, lammps, qe, custom",
  )
  spec_version: str = "0.1.0"
  input_uri: str | None = None
  output_uri: str | None = None
  status: str = "pending"  # pending, running, completed, failed
