from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mattergraph.normalization.properties import canonical_property_name


class PropertyMethod(str, Enum):
  DFT = "dft"
  EXPERIMENTAL = "experimental"
  MODEL_PREDICTED = "model_predicted"
  UNKNOWN = "unknown"


class MaterialProperty(BaseModel):
  """A provenance-aware property value attached to a material.

  JSON contract: enum values serialize as strings; unknown fields are rejected and should be
  placed in ``extra`` by callers that need source-specific metadata.
  """

  model_config = ConfigDict(extra="forbid", use_enum_values=True, validate_assignment=True)

  name: str = Field(description="Canonical property name, e.g. density or energy_above_hull")
  value: float | str | dict[str, Any]
  unit: str | None = Field(default=None, description="Unit string as supplied or normalized")
  source: str = Field(default="unknown", description="Database, experiment, or model source")
  method: PropertyMethod = PropertyMethod.UNKNOWN
  confidence: float | None = None
  uncertainty: float | None = None
  source_id: str | None = Field(
    default=None,
    description="Optional upstream property identifier, e.g. MP task ID or DOI field",
  )
  extra: dict[str, Any] = Field(default_factory=dict)

  @field_validator("name", "source")
  @classmethod
  def _non_empty_strings(cls, value: str, info: Any) -> str:
    out = value.strip()
    if not out:
      msg = f"{info.field_name} must not be empty"
      raise ValueError(msg)
    return canonical_property_name(out) if info.field_name == "name" else out

  @field_validator("unit")
  @classmethod
  def _strip_unit(cls, value: str | None) -> str | None:
    if value is None:
      return None
    out = value.strip()
    return out or None

  @field_validator("source_id")
  @classmethod
  def _strip_source_id(cls, value: str | None) -> str | None:
    if value is None:
      return None
    out = value.strip()
    return out or None

  @field_validator("confidence")
  @classmethod
  def _confidence_range(cls, value: float | None) -> float | None:
    if value is None:
      return None
    if not 0.0 <= value <= 1.0:
      msg = "confidence must be between 0 and 1"
      raise ValueError(msg)
    return value

  @field_validator("uncertainty")
  @classmethod
  def _non_negative_uncertainty(cls, value: float | None) -> float | None:
    if value is None:
      return None
    if value < 0:
      msg = "uncertainty must be non-negative"
      raise ValueError(msg)
    return value
