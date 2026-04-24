from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PropertyMethod(str, Enum):
  DFT = "dft"
  EXPERIMENTAL = "experimental"
  MODEL_PREDICTED = "model_predicted"
  UNKNOWN = "unknown"


class MaterialProperty(BaseModel):
  name: str
  value: float | str | dict[str, Any]
  unit: str | None = None
  source: str = "unknown"
  method: PropertyMethod = PropertyMethod.UNKNOWN
  confidence: float | None = None
  uncertainty: float | None = None
  extra: dict[str, Any] = Field(default_factory=dict)

  @field_validator("name", "source")
  @classmethod
  def _non_empty_strings(cls, value: str, info: Any) -> str:
    out = value.strip()
    if not out:
      msg = f"{info.field_name} must not be empty"
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

  @field_validator("uncertainty")
  @classmethod
  def _non_negative_uncertainty(cls, value: float | None) -> float | None:
    if value is None:
      return None
    if value < 0:
      msg = "uncertainty must be non-negative"
      raise ValueError(msg)
    return value
