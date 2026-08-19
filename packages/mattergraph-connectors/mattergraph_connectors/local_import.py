from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePath
from typing import Any, Literal

from mattergraph import DatasetManifest, Material, MaterialProperty
from mattergraph.schema.property import PropertyMethod
from mattergraph.schema.provenance import ProvenanceRecord
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_INPUT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 5_000
MAX_RETURNED_ISSUES = 100
MAX_PREVIEW_ROWS = 20


class PropertyColumnMapping(BaseModel):
  """Map one input column to a contextual, provenance-aware property."""

  model_config = ConfigDict(extra="forbid", use_enum_values=True)

  column: str
  name: str
  unit: str | None = None
  source: str = "local_file"
  method: PropertyMethod = PropertyMethod.UNKNOWN

  @field_validator("column", "name", "source")
  @classmethod
  def _non_empty(cls, value: str, info: Any) -> str:
    out = value.strip()
    if not out:
      msg = f"{info.field_name} must not be empty"
      raise ValueError(msg)
    return out

  @field_validator("unit")
  @classmethod
  def _strip_unit(cls, value: str | None) -> str | None:
    if value is None:
      return None
    out = value.strip()
    return out or None


class DatasetImportMapping(BaseModel):
  model_config = ConfigDict(extra="forbid")

  identity_column: str = "material_id"
  formula_column: str = "formula"
  structure_column: str | None = None
  source_id_column: str | None = None
  property_columns: list[PropertyColumnMapping] = Field(default_factory=list)

  @field_validator(
    "identity_column", "formula_column", "structure_column", "source_id_column"
  )
  @classmethod
  def _strip_columns(cls, value: str | None) -> str | None:
    if value is None:
      return None
    out = value.strip()
    return out or None

  @model_validator(mode="after")
  def _required_columns_present(self) -> DatasetImportMapping:
    if not self.identity_column or not self.formula_column:
      msg = "identity_column and formula_column are required"
      raise ValueError(msg)
    property_inputs = [mapping.column for mapping in self.property_columns]
    if len(property_inputs) != len(set(property_inputs)):
      msg = "a source column may be mapped to only one property"
      raise ValueError(msg)
    return self


class ImportIssue(BaseModel):
  model_config = ConfigDict(extra="forbid")

  code: str
  severity: Literal["error", "warning"]
  message: str
  row: int | None = Field(default=None, ge=1)
  column: str | None = None


class ImportReport(BaseModel):
  model_config = ConfigDict(extra="forbid")

  status: Literal["ready", "degraded", "invalid"]
  checksum: str
  row_count: int = Field(ge=0)
  accepted_count: int = Field(ge=0)
  rejected_count: int = Field(ge=0)
  columns: list[str] = Field(default_factory=list)
  inferred_mapping: DatasetImportMapping | None = None
  issues: list[ImportIssue] = Field(default_factory=list)
  issue_counts: dict[str, int] = Field(default_factory=dict)
  truncated_issue_count: int = Field(default=0, ge=0)


class ImportResult(BaseModel):
  model_config = ConfigDict(extra="forbid")

  dataset_id: str
  manifest: DatasetManifest
  accepted_count: int = Field(ge=0)
  rejected_count: int = Field(ge=0)
  issues: list[ImportIssue] = Field(default_factory=list)
  issue_counts: dict[str, int] = Field(default_factory=dict)
  truncated_issue_count: int = Field(default=0, ge=0)
  preview: list[dict[str, Any]] = Field(default_factory=list)


@dataclass(frozen=True)
class NormalizedImport:
  result: ImportResult
  normalized_jsonl: bytes


class LocalImportError(ValueError):
  pass


class ImportLimitError(LocalImportError):
  pass


class ImportValidationError(LocalImportError):
  def __init__(self, message: str, report: ImportReport) -> None:
    super().__init__(message)
    self.report = report


def inspect_local_content(
  *,
  filename: str,
  format: Literal["csv", "jsonl"],
  content: str,
) -> ImportReport:
  """Inspect a bounded local payload without registering or materializing it."""
  content_bytes = _validate_payload(content)
  rows, columns, parse_issues, row_count = _parse_rows(format, content)
  _validate_row_count(row_count)
  inferred = _infer_mapping(columns, format)
  issues = list(parse_issues)
  if row_count and inferred is not None:
    issues.extend(_mapping_issues(columns, inferred))
  return _report(
    checksum=hashlib.sha256(content_bytes).hexdigest(),
    rows=row_count,
    accepted=max(0, row_count - sum(issue.severity == "error" for issue in issues)),
    rejected=sum(issue.severity == "error" for issue in issues),
    columns=columns,
    mapping=inferred,
    issues=issues,
    status="invalid" if any(issue.severity == "error" for issue in issues) else "ready",
  )


def import_local_content(
  *,
  filename: str,
  format: Literal["csv", "jsonl"],
  content: str,
  mapping: DatasetImportMapping | None = None,
  error_policy: Literal["reject_file", "skip_invalid_rows"] = "reject_file",
) -> NormalizedImport:
  """Normalize a local payload into deterministic JSONL held only in memory."""
  content_bytes = _validate_payload(content)
  rows, columns, parse_issues, row_count = _parse_rows(format, content)
  _validate_row_count(row_count)
  selected_mapping = mapping or _infer_mapping(columns, format)
  if selected_mapping is None:
    selected_mapping = DatasetImportMapping()

  issues = [*parse_issues, *_mapping_issues(columns, selected_mapping)]
  normalized_buffer = bytearray()
  preview: list[dict[str, Any]] = []
  accepted_count = 0
  seen_ids: set[str] = set()
  content_sha256 = hashlib.sha256(content_bytes).hexdigest()
  for row_number, row in rows:
    try:
      material = _row_to_material(
        row,
        row_number=row_number,
        filename=filename,
        format=format,
        mapping=selected_mapping,
        content_sha256=content_sha256,
      )
      if material.material_id in seen_ids:
        msg = f"duplicate material ID {material.material_id!r}"
        raise ValueError(msg)
      seen_ids.add(material.material_id)
      normalized_record = material.model_dump(mode="json", exclude_none=True)
      normalized_buffer.extend(
        json.dumps(normalized_record, sort_keys=True).encode("utf-8") + b"\n"
      )
      if len(preview) < MAX_PREVIEW_ROWS:
        preview.append(normalized_record)
      accepted_count += 1
    except (TypeError, ValueError, json.JSONDecodeError) as error:
      issues.append(
        ImportIssue(
          code=_issue_code(error),
          severity="error",
          row=row_number,
          message=str(error),
        )
      )

  rejected_count = sum(issue.row is not None and issue.severity == "error" for issue in issues)
  status: Literal["ready", "degraded", "invalid"] = "ready"
  if any(issue.severity == "error" and issue.row is None for issue in issues):
    status = "invalid"
  elif rejected_count:
    status = "degraded" if error_policy == "skip_invalid_rows" else "invalid"
  report = _report(
    checksum=content_sha256,
    rows=row_count,
    accepted=accepted_count,
    rejected=rejected_count,
    columns=columns,
    mapping=selected_mapping,
    issues=issues,
    status=status,
  )
  if status == "invalid":
    raise ImportValidationError("local dataset failed strict validation", report)
  if not accepted_count:
    report = report.model_copy(update={"status": "invalid"})
    raise ImportValidationError("local dataset must contain at least one valid row", report)

  normalized_bytes = bytes(normalized_buffer)
  if len(normalized_bytes) > MAX_INPUT_BYTES:
    msg = f"normalized payload exceeds {MAX_INPUT_BYTES} bytes"
    raise ImportLimitError(msg)
  normalized_sha256 = hashlib.sha256(normalized_bytes).hexdigest()
  dataset_id = f"mg_ds_{normalized_sha256[:16]}"
  display_name = _safe_filename(filename)
  manifest = DatasetManifest(
    dataset_id=dataset_id,
    name=display_name,
    source="local_file",
    format=format,
    record_count=accepted_count,
    accepted_count=accepted_count,
    rejected_count=rejected_count,
    content_sha256=content_sha256,
    normalized_sha256=normalized_sha256,
    normalized_bytes=len(normalized_bytes),
    degraded=status == "degraded",
  )
  bounded_issues, counts, truncated = _bounded_issues(issues)
  return NormalizedImport(
    result=ImportResult(
      dataset_id=dataset_id,
      manifest=manifest,
      accepted_count=accepted_count,
      rejected_count=rejected_count,
      issues=bounded_issues,
      issue_counts=counts,
      truncated_issue_count=truncated,
      preview=preview,
    ),
    normalized_jsonl=normalized_bytes,
  )


def _validate_payload(content: str) -> bytes:
  content_bytes = content.encode("utf-8")
  if len(content_bytes) > MAX_INPUT_BYTES:
    msg = f"input exceeds {MAX_INPUT_BYTES} bytes"
    raise ImportLimitError(msg)
  if not content.strip():
    report = _report(
      checksum=hashlib.sha256(content_bytes).hexdigest(),
      rows=0,
      accepted=0,
      rejected=0,
      columns=[],
      mapping=None,
      issues=[ImportIssue(code="empty_file", severity="error", message="file is empty")],
      status="invalid",
    )
    raise ImportValidationError("file is empty", report)
  return content_bytes


def _validate_row_count(count: int) -> None:
  if count > MAX_IMPORT_ROWS:
    msg = f"input contains {count} rows; maximum is {MAX_IMPORT_ROWS}"
    raise ImportLimitError(msg)


def _parse_rows(
  format: Literal["csv", "jsonl"], content: str
) -> tuple[list[tuple[int, dict[str, Any]]], list[str], list[ImportIssue], int]:
  if format == "csv":
    try:
      reader = csv.DictReader(io.StringIO(content))
      columns = list(reader.fieldnames or [])
      if not columns:
        msg = "CSV must contain a header row"
        raise ValueError(msg)
      rows = [(index, dict(row)) for index, row in enumerate(reader, start=1)]
      return rows, columns, [], len(rows)
    except csv.Error as error:
      msg = f"malformed CSV: {error}"
      raise LocalImportError(msg) from error

  rows: list[tuple[int, dict[str, Any]]] = []
  columns: list[str] = []
  issues: list[ImportIssue] = []
  row_count = 0
  for line_number, line in enumerate(content.splitlines(), start=1):
    if not line.strip():
      continue
    row_count += 1
    try:
      value = json.loads(line)
      if not isinstance(value, dict):
        msg = "JSONL rows must be objects"
        raise ValueError(msg)
      rows.append((line_number, value))
      for key in value:
        if key not in columns:
          columns.append(key)
    except (json.JSONDecodeError, ValueError) as error:
      issues.append(
        ImportIssue(
          code="malformed_jsonl",
          severity="error",
          row=line_number,
          message=str(error),
        )
      )
  return rows, columns, issues, row_count


def _infer_mapping(columns: list[str], format: Literal["csv", "jsonl"]) -> DatasetImportMapping:
  identity = next(
    (name for name in ("material_id", "id", "identifier") if name in columns),
    "material_id",
  )
  formula = next(
    (name for name in ("formula", "composition", "reduced_formula") if name in columns),
    "formula",
  )
  structure = next(
    (name for name in ("structure", "structure_json", "cif") if name in columns),
    None,
  )
  source_id = "source_id" if "source_id" in columns else None
  reserved = {
    identity,
    formula,
    structure,
    source_id,
    "properties",
    "provenance",
    "metadata",
    "elements",
    "reduced_formula",
    "dimensionality",
  }
  properties = [] if format == "jsonl" and "properties" in columns else [
    PropertyColumnMapping(column=column, name=column)
    for column in columns
    if column not in reserved
  ]
  return DatasetImportMapping(
    identity_column=identity,
    formula_column=formula,
    structure_column=structure,
    source_id_column=source_id,
    property_columns=properties,
  )


def _mapping_issues(columns: list[str], mapping: DatasetImportMapping) -> list[ImportIssue]:
  issues: list[ImportIssue] = []
  for required in (mapping.identity_column, mapping.formula_column):
    if required not in columns:
      issues.append(
        ImportIssue(
          code="missing_identity_column",
          severity="error",
          column=required,
          message=f"required column {required!r} is missing",
        )
      )
  optional = [mapping.structure_column, mapping.source_id_column]
  optional.extend(property.column for property in mapping.property_columns)
  for column in optional:
    if column is not None and column not in columns:
      issues.append(
        ImportIssue(
          code="unknown_mapping_column",
          severity="error",
          column=column,
          message=f"mapped column {column!r} is missing",
        )
      )
  for property_mapping in mapping.property_columns:
    if property_mapping.unit and not _looks_like_unit(property_mapping.unit):
      issues.append(
        ImportIssue(
          code="unknown_unit",
          severity="warning",
          column=property_mapping.column,
          message=f"unit {property_mapping.unit!r} is retained verbatim and was not recognized",
        )
      )
  methods = {property.method for property in mapping.property_columns}
  if len(methods) > 1:
    issues.append(
      ImportIssue(
        code="mixed_methods",
        severity="warning",
        message="property mappings contain more than one method; provenance remains per property",
      )
    )
  return issues


def _row_to_material(
  row: dict[str, Any],
  *,
  row_number: int,
  filename: str,
  format: Literal["csv", "jsonl"],
  mapping: DatasetImportMapping,
  content_sha256: str,
) -> Material:
  if format == "jsonl" and "properties" in row:
    material = Material.model_validate(row)
    provenance = [
      *material.provenance,
      ProvenanceRecord(
        source="local_file",
        source_id=_safe_filename(filename),
        parameters={"content_sha256": content_sha256, "row": row_number},
      ),
    ]
    return material.model_copy(update={"provenance": provenance})

  identity = _required_value(row, mapping.identity_column)
  formula = _required_value(row, mapping.formula_column)
  structure = None
  if mapping.structure_column:
    raw_structure = row.get(mapping.structure_column)
    if raw_structure not in (None, ""):
      if isinstance(raw_structure, str):
        raw_structure = json.loads(raw_structure)
      if not isinstance(raw_structure, dict):
        msg = "structure must be a JSON object"
        raise ValueError(msg)
      structure = raw_structure
  properties: list[MaterialProperty] = []
  for property_mapping in mapping.property_columns:
    raw = row.get(property_mapping.column)
    if raw in (None, ""):
      continue
    properties.append(
      MaterialProperty(
        name=property_mapping.name,
        value=_coerce_value(raw),
        unit=property_mapping.unit,
        source=property_mapping.source,
        method=property_mapping.method,
        source_id=str(row.get(mapping.source_id_column))
        if mapping.source_id_column and row.get(mapping.source_id_column) not in (None, "")
        else None,
      )
    )
  source_id = None
  if mapping.source_id_column and row.get(mapping.source_id_column) not in (None, ""):
    source_id = str(row[mapping.source_id_column])
  return Material(
    material_id=str(identity),
    formula=str(formula),
    structure=structure,
    properties=properties,
    source_id=source_id,
    provenance=[
      ProvenanceRecord(
        source="local_file",
        source_id=_safe_filename(filename),
        parameters={"content_sha256": content_sha256, "row": row_number},
      )
    ],
    metadata={"ingest": "local_import", "filename": _safe_filename(filename)},
  )


def _required_value(row: dict[str, Any], column: str) -> Any:
  value = row.get(column)
  if value is None or (isinstance(value, str) and not value.strip()):
    msg = f"required identity field {column!r} is empty"
    raise ValueError(msg)
  return value


def _coerce_value(value: Any) -> float | str | dict[str, Any]:
  if isinstance(value, (int, float)):
    numeric = float(value)
    if not math.isfinite(numeric):
      msg = "property values must be finite"
      raise ValueError(msg)
    return numeric
  if isinstance(value, dict):
    return value
  text = str(value).strip()
  try:
    numeric = float(text)
    if math.isfinite(numeric):
      return numeric
  except ValueError:
    pass
  if text.startswith("{"):
    parsed = json.loads(text)
    if isinstance(parsed, dict):
      return parsed
  return text


def _report(
  *,
  checksum: str,
  rows: int,
  accepted: int,
  rejected: int,
  columns: list[str],
  mapping: DatasetImportMapping | None,
  issues: list[ImportIssue],
  status: Literal["ready", "degraded", "invalid"],
) -> ImportReport:
  bounded, counts, truncated = _bounded_issues(issues)
  return ImportReport(
    status=status,
    checksum=checksum,
    row_count=rows,
    accepted_count=accepted,
    rejected_count=rejected,
    columns=columns,
    inferred_mapping=mapping,
    issues=bounded,
    issue_counts=counts,
    truncated_issue_count=truncated,
  )


def _bounded_issues(
  issues: list[ImportIssue],
) -> tuple[list[ImportIssue], dict[str, int], int]:
  counts = dict(Counter(issue.code for issue in issues))
  bounded = issues[:MAX_RETURNED_ISSUES]
  return bounded, counts, max(0, len(issues) - len(bounded))


def _issue_code(error: Exception) -> str:
  message = str(error).lower()
  if "structure" in message or "lattice" in message or "species" in message:
    return "invalid_structure"
  if "formula" in message or "composition" in message:
    return "invalid_formula"
  if "required identity" in message:
    return "missing_identity"
  if "duplicate" in message:
    return "duplicate_id"
  return "invalid_row"


def _looks_like_unit(unit: str) -> bool:
  known_fragments = (
    "ev",
    "g/cm",
    "kg/m",
    "gpa",
    "mpa",
    "kpa",
    "pa",
    "kelvin",
    "angstrom",
    "å",
    "nm",
    "k",
    "%",
  )
  normalized = unit.strip().lower()
  return any(fragment in normalized for fragment in known_fragments)


def _safe_filename(filename: str) -> str:
  return PurePath(filename.replace("\\", "/")).name or "local-dataset"
