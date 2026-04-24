from pydantic import BaseModel, ConfigDict, Field, field_validator

from mattergraph.schema.property import PropertyMethod


class ProvenanceRecord(BaseModel):
  """Lineage and confidence for a value or field.

  JSON contract: enum values serialize as strings; source-specific fields belong in ``extra``.
  """

  model_config = ConfigDict(extra="forbid", use_enum_values=True, validate_assignment=True)

  source: str
  method: PropertyMethod = Field(
    default=PropertyMethod.UNKNOWN,
    description="e.g. dft, experiment, model_predicted",
  )
  confidence: float | None = None
  notes: str | None = None
  model_version: str | None = None
  source_id: str | None = Field(
    default=None,
    description="Optional upstream record identifier, task ID, DOI, or dataset row ID",
  )

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

  @field_validator("source_id", "model_version", "notes")
  @classmethod
  def _strip_optional_strings(cls, value: str | None) -> str | None:
    if value is None:
      return None
    out = value.strip()
    return out or None
