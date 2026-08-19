from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DatasetManifest(BaseModel):
  """Compact, public metadata for a reproducible material dataset snapshot."""

  model_config = ConfigDict(extra="forbid", validate_assignment=True)

  schema_version: Literal["0.1"] = "0.1"
  dataset_id: str
  name: str
  source: str = "local_file"
  format: Literal["csv", "jsonl", "normalized_jsonl"]
  record_count: int = Field(ge=0)
  accepted_count: int = Field(ge=0)
  rejected_count: int = Field(ge=0)
  content_sha256: str
  normalized_sha256: str
  normalized_bytes: int = Field(ge=0)
  degraded: bool = False
  created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

  @field_validator("dataset_id", "name", "source")
  @classmethod
  def _non_empty_strings(cls, value: str, info: object) -> str:
    out = value.strip()
    if not out:
      field_name = getattr(info, "field_name", "value")
      msg = f"{field_name} must not be empty"
      raise ValueError(msg)
    return out

  @field_validator("content_sha256", "normalized_sha256")
  @classmethod
  def _valid_sha256(cls, value: str) -> str:
    out = value.strip().lower()
    if len(out) != 64 or any(character not in "0123456789abcdef" for character in out):
      msg = "checksums must be 64-character hexadecimal SHA-256 digests"
      raise ValueError(msg)
    return out
