from pydantic import BaseModel, Field, field_validator

from mattergraph.schema.property import PropertyMethod


class ProvenanceRecord(BaseModel):
  """Lineage and confidence for a value or field."""

  source: str
  method: PropertyMethod = Field(
    default=PropertyMethod.UNKNOWN,
    description="e.g. dft, experiment, model_predicted",
  )
  confidence: float | None = None
  notes: str | None = None
  model_version: str | None = None

  @field_validator("source")
  @classmethod
  def _non_empty_source(cls, value: str) -> str:
    out = value.strip()
    if not out:
      msg = "source must not be empty"
      raise ValueError(msg)
    return out

  @field_validator("confidence")
  @classmethod
  def _confidence_range(cls, value: float | None) -> float | None:
    if value is None:
      return None
    if not 0.0 <= value <= 1.0:
      msg = "confidence must be between 0 and 1"
      raise ValueError(msg)
    return value
