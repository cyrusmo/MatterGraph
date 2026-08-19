from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mattergraph.schema.context import SourceArtifact
from mattergraph.schema.property import MaterialProperty
from mattergraph.schema.provenance import ProvenanceRecord


class SimulationResultEnvelope(BaseModel):
  """Engine-neutral interchange envelope for imported simulation results.

  It records evidence and reproducibility metadata without implying orchestration,
  qualification, or approval.
  """

  model_config = ConfigDict(extra="forbid", validate_assignment=True)

  engine: str
  engine_version: str | None = None
  method: str
  parameters: dict[str, Any] = Field(default_factory=dict)
  input_checksum_sha256: str
  output_checksum_sha256: str | None = None
  converged: bool | None = None
  properties: list[MaterialProperty] = Field(default_factory=list)
  artifacts: list[SourceArtifact] = Field(default_factory=list)
  provenance: list[ProvenanceRecord] = Field(default_factory=list)

  @field_validator("engine", "method")
  @classmethod
  def _non_empty_strings(cls, value: str) -> str:
    out = value.strip()
    if not out:
      msg = "engine and method must not be empty"
      raise ValueError(msg)
    return out

  @field_validator("engine_version")
  @classmethod
  def _strip_engine_version(cls, value: str | None) -> str | None:
    if value is None:
      return None
    out = value.strip()
    return out or None

  @field_validator("input_checksum_sha256", "output_checksum_sha256")
  @classmethod
  def _valid_sha256(cls, value: str | None) -> str | None:
    if value is None:
      return None
    out = value.strip().lower()
    if len(out) != 64 or any(character not in "0123456789abcdef" for character in out):
      msg = "checksums must be 64-character hexadecimal SHA-256 digests"
      raise ValueError(msg)
    return out
