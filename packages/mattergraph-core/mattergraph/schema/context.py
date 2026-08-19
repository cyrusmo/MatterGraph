from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Quantity(BaseModel):
  """A scalar quantity whose unit is explicit at the JSON boundary."""

  model_config = ConfigDict(extra="forbid", validate_assignment=True)

  value: float
  unit: str

  @field_validator("value")
  @classmethod
  def _finite_value(cls, value: float) -> float:
    if not math.isfinite(value):
      msg = "quantity value must be finite"
      raise ValueError(msg)
    return value

  @field_validator("unit")
  @classmethod
  def _non_empty_unit(cls, value: str) -> str:
    out = value.strip()
    if not out:
      msg = "quantity unit must not be empty"
      raise ValueError(msg)
    return out


class SourceArtifact(BaseModel):
  """Public citation and integrity metadata for an upstream artifact."""

  model_config = ConfigDict(extra="forbid", validate_assignment=True)

  citation: str | None = None
  doi: str | None = None
  uri: str | None = None
  revision: str | None = None
  page: str | None = None
  license: str | None = None
  checksum_sha256: str | None = Field(
    default=None,
    description="Lower-case SHA-256 digest of the referenced artifact",
  )

  @field_validator("citation", "doi", "uri", "revision", "page", "license")
  @classmethod
  def _strip_optional_strings(cls, value: str | None) -> str | None:
    if value is None:
      return None
    out = value.strip()
    return out or None

  @field_validator("checksum_sha256")
  @classmethod
  def _valid_sha256(cls, value: str | None) -> str | None:
    if value is None:
      return None
    out = value.strip().lower()
    if len(out) != 64 or any(character not in "0123456789abcdef" for character in out):
      msg = "checksum_sha256 must be a 64-character hexadecimal digest"
      raise ValueError(msg)
    return out

  @model_validator(mode="after")
  def _has_reference(self) -> SourceArtifact:
    if not any(self.model_dump(exclude_none=True).values()):
      msg = "source artifact must include at least one reference field"
      raise ValueError(msg)
    return self


class PropertyContext(BaseModel):
  """Decision-neutral conditions under which a property applies."""

  model_config = ConfigDict(extra="forbid", validate_assignment=True)

  temperature: Quantity | None = None
  pressure: Quantity | None = None
  environment: str | None = None
  orientation: str | None = None
  material_state: str | None = None
  process_route: str | None = None
  specimen: str | None = None
  test_method: str | None = None
  instrument: str | None = None
  statistical_basis: str | None = None
  applicability: str | None = None

  @field_validator(
    "environment",
    "orientation",
    "material_state",
    "process_route",
    "specimen",
    "test_method",
    "instrument",
    "statistical_basis",
    "applicability",
  )
  @classmethod
  def _strip_optional_strings(cls, value: str | None) -> str | None:
    if value is None:
      return None
    out = value.strip()
    return out or None
