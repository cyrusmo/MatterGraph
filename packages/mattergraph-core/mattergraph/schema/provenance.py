from pydantic import BaseModel, Field


class ProvenanceRecord(BaseModel):
  """Lineage and confidence for a value or field."""

  source: str
  method: str = Field(
    default="unknown",
    description="e.g. dft, experiment, model_predicted",
  )
  confidence: float | None = None
  notes: str | None = None
  model_version: str | None = None
