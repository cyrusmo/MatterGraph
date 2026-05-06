from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Literal

import pandas as pd
from mattergraph.graph.crystal_graph import CrystalGraphBuilder
from mattergraph.normalization.formulas import reduced_formula as normalize_reduced_formula
from mattergraph.schema.material import Material
from mattergraph.schema.property import MaterialProperty, PropertyMethod
from mattergraph.schema.provenance import ProvenanceRecord
from mattergraph.schema.structure import CrystalStructure
from mattergraph.store import MaterialStore

DeduplicationBasis = Literal[
  "none",
  "immutable_id",
  "structure_fingerprint",
  "formula_only",
  "custom",
  "unknown",
]

_STANDARD_COLUMNS = {
  "material_id",
  "formula",
  "reduced_formula",
  "elements",
  "nelements",
  "nsites",
  "structure",
  "functional",
  "immutable_id",
  "structure_fingerprint",
  "provenance",
  "source_dataset",
  "source_subset",
}
_PROVENANCE_COLUMNS = {
  "functional",
  "immutable_id",
  "source_dataset",
  "source_subset",
  "structure_fingerprint",
}


@dataclass(frozen=True)
class GraphExportResult:
  graphs: list[dict[str, Any]]
  included_count: int
  excluded_count: int


@dataclass(frozen=True)
class CandidateSlice:
  slice_name: str
  source_dataset: str
  source_subset: str | None
  input_count: int
  output_count: int
  filter_steps: tuple[dict[str, Any], ...]
  guardrail_config: dict[str, Any]
  duplicate_policy: str
  deduplication_basis: DeduplicationBasis
  provenance_fields_preserved: tuple[str, ...]
  frame: pd.DataFrame = field(repr=False)
  target: str | None = None
  graph_export_excluded_count: int = 0
  slice_id: str = field(init=False)

  def __post_init__(self) -> None:
    payload = {
      "source_dataset": self.source_dataset,
      "source_subset": self.source_subset,
      "filter_steps": [
        {
          "name": step["name"],
          "arguments": step["arguments"],
        }
        for step in self.filter_steps
      ],
      "guardrail_config": self.guardrail_config,
      "deduplication_basis": self.deduplication_basis,
      "target": self.target,
    }
    digest = sha256(
      json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:12]
    object.__setattr__(self, "slice_id", f"mg_slice_{digest}")

  def report(self) -> dict[str, Any]:
    columns_used = sorted(
      {
        column
        for step in self.filter_steps
        for column in step.get("columns_used", [])
      }
    )
    duplicate_signals = _duplicate_signals(self.frame)
    return {
      "slice_id": self.slice_id,
      "slice_name": self.slice_name,
      "source_dataset": self.source_dataset,
      "source_subset": self.source_subset,
      "input_count": self.input_count,
      "output_count": self.output_count,
      "removed_count": self.input_count - self.output_count,
      "filter_steps": list(self.filter_steps),
      "columns_used": columns_used,
      "mixed_functionals": _mixed_functionals(self.frame),
      "duplicate_policy": self.duplicate_policy,
      "deduplication_basis": self.deduplication_basis,
      "provenance_fields_preserved": list(self.provenance_fields_preserved),
      "missing_structure_count": _missing_structure_count(self.frame),
      "graph_export_excluded_count": self.graph_export_excluded_count,
      "duplicate_signals": duplicate_signals,
    }


class MatterGraphDataset:
  """Immutable-ish workflow wrapper over normalized tabular materials records."""

  def __init__(
    self,
    frame: pd.DataFrame,
    *,
    source_dataset: str,
    source_subset: str | None = None,
    metadata: dict[str, Any] | None = None,
    filter_steps: list[dict[str, Any]] | None = None,
    root_input_count: int | None = None,
  ) -> None:
    self._frame = _normalize_dataset_frame(frame)
    self.source_dataset = source_dataset
    self.source_subset = source_subset
    self.metadata = dict(metadata or {})
    self._filter_steps = list(filter_steps or [])
    self._root_input_count = root_input_count if root_input_count is not None else len(self._frame)

  @classmethod
  def from_records(
    cls,
    records: list[dict[str, Any]],
    *,
    source_dataset: str,
    source_subset: str | None = None,
    metadata: dict[str, Any] | None = None,
  ) -> MatterGraphDataset:
    return cls(
      pd.DataFrame(records),
      source_dataset=source_dataset,
      source_subset=source_subset,
      metadata=metadata,
    )

  def __len__(self) -> int:
    return len(self._frame)

  def to_pandas(self) -> pd.DataFrame:
    return self._frame.copy(deep=True)

  def schema_report(self) -> dict[str, Any]:
    return {
      "source_dataset": self.source_dataset,
      "source_subset": self.source_subset,
      "row_count": len(self._frame),
      "columns": list(self._frame.columns),
      "functional_coverage": _value_counts(self._frame.get("functional")),
      "mixed_functionals": _mixed_functionals(self._frame),
      "duplicate_signals": _duplicate_signals(self._frame),
      "deduplication_basis": self.default_deduplication_basis,
      "immutable_id_coverage": int(self._frame["immutable_id"].notna().sum())
      if "immutable_id" in self._frame.columns
      else 0,
      "structure_fingerprint_coverage": int(self._frame["structure_fingerprint"].notna().sum())
      if "structure_fingerprint" in self._frame.columns
      else 0,
      "missing_structure_count": _missing_structure_count(self._frame),
      "provenance_fields_preserved": self.provenance_fields_preserved,
    }

  @property
  def default_deduplication_basis(self) -> DeduplicationBasis:
    basis = self.metadata.get("default_deduplication_basis", "unknown")
    return basis if basis in _allowed_deduplication_bases() else "unknown"

  @property
  def provenance_fields_preserved(self) -> list[str]:
    metadata_fields = self.metadata.get("provenance_fields", [])
    present = {field for field in metadata_fields if field in self._frame.columns or field in _PROVENANCE_COLUMNS}
    present.update({field for field in _PROVENANCE_COLUMNS if field in self._frame.columns})
    return sorted(present)

  def element_counts(self) -> pd.Series:
    counter: Counter[str] = Counter()
    for elements in self._frame["elements"]:
      counter.update(sorted(set(elements)))
    if not counter:
      return pd.Series(dtype="int64")
    return pd.Series(dict(counter)).sort_values(ascending=False)

  def filter_elements(
    self,
    *,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
  ) -> MatterGraphDataset:
    include_set = {element.strip() for element in include or [] if element.strip()}
    exclude_set = {element.strip() for element in exclude or [] if element.strip()}
    mask = pd.Series(True, index=self._frame.index)
    if include_set:
      mask &= self._frame["elements"].apply(
        lambda elements: bool(elements) and set(elements).issubset(include_set)
      )
    if exclude_set:
      mask &= self._frame["elements"].apply(lambda elements: exclude_set.isdisjoint(elements))
    return self._filtered(
      self._frame.loc[mask].reset_index(drop=True),
      name="filter_elements",
      arguments={"include": sorted(include_set) or None, "exclude": sorted(exclude_set) or None},
      columns_used=["elements"],
      input_count=len(self._frame),
    )

  def filter_complexity(
    self,
    *,
    max_nsites: int | None = None,
    max_nelements: int | None = None,
  ) -> MatterGraphDataset:
    mask = pd.Series(True, index=self._frame.index)
    columns_used: list[str] = []
    if max_nsites is not None:
      columns_used.append("nsites")
      mask &= self._frame["nsites"].apply(lambda value: value is not None and int(value) <= max_nsites)
    if max_nelements is not None:
      columns_used.append("nelements")
      mask &= self._frame["nelements"].apply(
        lambda value: value is not None and int(value) <= max_nelements
      )
    return self._filtered(
      self._frame.loc[mask].reset_index(drop=True),
      name="filter_complexity",
      arguments={"max_nsites": max_nsites, "max_nelements": max_nelements},
      columns_used=columns_used,
      input_count=len(self._frame),
    )

  def candidate_pool(
    self,
    *,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    max_nsites: int | None = None,
    max_nelements: int | None = None,
  ) -> MatterGraphDataset:
    dataset = self
    if include or exclude:
      dataset = dataset.filter_elements(include=include, exclude=exclude)
    if max_nsites is not None or max_nelements is not None:
      dataset = dataset.filter_complexity(
        max_nsites=max_nsites,
        max_nelements=max_nelements,
      )
    return dataset

  def to_material_store(self) -> MaterialStore:
    materials = [self._row_to_material(row) for row in self._frame.to_dict(orient="records")]
    return MaterialStore(materials=materials)

  def to_graphs(
    self,
    *,
    builder: CrystalGraphBuilder | None = None,
    cutoff_radius: float = 5.0,
    max_neighbors: int = 12,
  ) -> GraphExportResult:
    graph_builder = builder or CrystalGraphBuilder(
      cutoff_radius=cutoff_radius,
      max_neighbors=max_neighbors,
    )
    graphs: list[dict[str, Any]] = []
    excluded_count = 0
    for row in self._frame.to_dict(orient="records"):
      structure = row.get("structure")
      if not isinstance(structure, CrystalStructure):
        excluded_count += 1
        continue
      graph = graph_builder.build(structure)
      graphs.append(
        {
          "material_id": row["material_id"],
          "graph": graph,
          "metadata": {
            "formula": row["formula"],
            "functional": row.get("functional"),
          },
        }
      )
    return GraphExportResult(
      graphs=graphs,
      included_count=len(graphs),
      excluded_count=excluded_count,
    )

  def create_slice(
    self,
    slice_name: str,
    *,
    allow_mixed_functionals: bool = False,
    allow_duplicate_records: bool = False,
    deduplication_basis: DeduplicationBasis | None = None,
    target: str | None = None,
  ) -> CandidateSlice:
    basis = deduplication_basis or self.default_deduplication_basis
    if basis == "formula_only" and deduplication_basis is None:
      msg = "formula_only deduplication must be explicitly requested"
      raise ValueError(msg)
    if target is not None and target not in self._frame.columns:
      msg = f"target column {target!r} is not present in the dataset"
      raise ValueError(msg)

    strict_guardrails = bool(self.metadata.get("strict_guardrails", False))
    if strict_guardrails and not allow_mixed_functionals and _mixed_functionals(self._frame):
      msg = "Mixed functionals are blocked by default; pass allow_mixed_functionals=True to continue"
      raise ValueError(msg)
    duplicate_signals = _duplicate_signals(self._frame)
    if not allow_duplicate_records:
      if duplicate_signals["exact_record_duplicate_count"] > 0:
        msg = "Exact repeated records are blocked by default; pass allow_duplicate_records=True to continue"
        raise ValueError(msg)
      if strict_guardrails and basis == "unknown":
        msg = (
          "Duplicate-sensitive slice creation is blocked because the deduplication basis is "
          "unknown; pass allow_duplicate_records=True to continue"
        )
        raise ValueError(msg)
      if basis == "immutable_id" and duplicate_signals["immutable_id_collision_count"] > 0:
        msg = "Immutable-id collisions are blocked by default; pass allow_duplicate_records=True to continue"
        raise ValueError(msg)
      if basis == "structure_fingerprint" and duplicate_signals["structure_fingerprint_collision_count"] > 0:
        msg = (
          "Structure-fingerprint collisions are blocked by default; "
          "pass allow_duplicate_records=True to continue"
        )
        raise ValueError(msg)
      if basis == "formula_only" and duplicate_signals["formula_multiplicity_count"] > 0:
        msg = "Formula-only duplicate handling is blocked by default; pass allow_duplicate_records=True to continue"
        raise ValueError(msg)

    return CandidateSlice(
      slice_name=slice_name,
      source_dataset=self.source_dataset,
      source_subset=self.source_subset,
      input_count=self._root_input_count,
      output_count=len(self._frame),
      filter_steps=tuple(self._filter_steps),
      guardrail_config={
        "allow_mixed_functionals": allow_mixed_functionals,
        "allow_duplicate_records": allow_duplicate_records,
        "strict_guardrails": strict_guardrails,
      },
      duplicate_policy=(
        "allow_duplicate_records" if allow_duplicate_records else "disallow_duplicate_records"
      ),
      deduplication_basis=basis,
      provenance_fields_preserved=tuple(self.provenance_fields_preserved),
      frame=self._frame.copy(deep=True),
      target=target,
      graph_export_excluded_count=0,
    )

  def to_benchmark_frame(self, target: str | None = None) -> pd.DataFrame:
    if target is not None and target not in self._frame.columns:
      msg = f"target column {target!r} is not present in the dataset"
      raise ValueError(msg)
    frame = self._frame.copy(deep=True)
    frame["source_dataset"] = self.source_dataset
    frame["source_subset"] = self.source_subset
    frame["structure"] = frame["structure"].apply(
      lambda value: value.to_json_dict() if isinstance(value, CrystalStructure) else None
    )
    if target is not None:
      frame["target"] = frame[target]
    return frame

  def _filtered(
    self,
    frame: pd.DataFrame,
    *,
    name: str,
    arguments: dict[str, Any],
    columns_used: list[str],
    input_count: int,
  ) -> MatterGraphDataset:
    step = {
      "name": name,
      "arguments": arguments,
      "columns_used": columns_used,
      "input_count": input_count,
      "output_count": len(frame),
      "removed_count": input_count - len(frame),
    }
    return MatterGraphDataset(
      frame,
      source_dataset=self.source_dataset,
      source_subset=self.source_subset,
      metadata=self.metadata,
      filter_steps=[*self._filter_steps, step],
      root_input_count=self._root_input_count,
    )

  def _row_to_material(self, row: dict[str, Any]) -> Material:
    property_columns = list(self.metadata.get("property_columns", _infer_property_columns(self._frame)))
    properties: list[MaterialProperty] = []
    for column in property_columns:
      value = row.get(column)
      if _is_missing(value):
        continue
      if isinstance(value, (list, tuple)):
        continue
      properties.append(
        MaterialProperty(
          name=column,
          value=_coerce_property_value(value),
          source=self.source_dataset,
          method=_property_method_from_row(row),
        )
      )
    provenance = _coerce_provenance(row.get("provenance"))
    if not provenance:
      provenance = [
        ProvenanceRecord(
          source=self.source_dataset,
          method=_property_method_from_row(row),
        )
      ]
    structure = row.get("structure")
    metadata = {
      "source_dataset": self.source_dataset,
      "source_subset": self.source_subset,
    }
    for key in ("functional", "immutable_id", "structure_fingerprint"):
      if not _is_missing(row.get(key)):
        metadata[key] = row[key]
    return Material(
      material_id=str(row["material_id"]),
      formula=str(row["formula"]),
      reduced_formula=str(row["reduced_formula"]),
      elements=list(row["elements"]),
      structure=structure if isinstance(structure, CrystalStructure) else None,
      properties=properties,
      provenance=provenance,
      metadata=metadata,
    )


def _allowed_deduplication_bases() -> set[str]:
  return {"none", "immutable_id", "structure_fingerprint", "formula_only", "custom", "unknown"}


def _normalize_dataset_frame(frame: pd.DataFrame) -> pd.DataFrame:
  normalized = frame.copy(deep=True)
  if "material_id" not in normalized.columns:
    msg = "dataset must include a material_id column"
    raise ValueError(msg)
  if "formula" not in normalized.columns:
    msg = "dataset must include a formula column"
    raise ValueError(msg)
  normalized["material_id"] = normalized["material_id"].apply(lambda value: str(value).strip())
  normalized["formula"] = normalized["formula"].apply(lambda value: str(value).strip())
  normalized["reduced_formula"] = normalized.get("reduced_formula", normalized["formula"]).apply(
    lambda value: normalize_reduced_formula(str(value))
  )
  normalized["elements"] = normalized.get("elements", normalized["formula"]).apply(_coerce_elements)
  normalized["nelements"] = normalized.get("nelements", normalized["elements"].apply(len)).apply(
    _coerce_optional_int
  )
  if "structure" not in normalized.columns:
    normalized["structure"] = None
  normalized["structure"] = normalized["structure"].apply(_coerce_structure)
  normalized["nsites"] = normalized.get(
    "nsites",
    normalized["structure"].apply(lambda value: len(value.species) if isinstance(value, CrystalStructure) else None),
  ).apply(_coerce_optional_int)
  for optional_column in ("functional", "immutable_id", "structure_fingerprint", "provenance"):
    if optional_column not in normalized.columns:
      normalized[optional_column] = None
  return normalized.reset_index(drop=True)


def _coerce_optional_int(value: Any) -> int | None:
  if _is_missing(value):
    return None
  return int(value)


def _coerce_elements(value: Any) -> list[str]:
  if isinstance(value, list):
    return sorted({str(element).strip() for element in value if str(element).strip()})
  if isinstance(value, tuple):
    return sorted({str(element).strip() for element in value if str(element).strip()})
  if isinstance(value, str):
    stripped = value.strip()
    if not stripped:
      return []
    if stripped.startswith("["):
      loaded = json.loads(stripped)
      if isinstance(loaded, list):
        return sorted({str(element).strip() for element in loaded if str(element).strip()})
    try:
      from pymatgen.core import Composition

      return sorted(str(element) for element in Composition(stripped).elements)
    except Exception:
      separators = [",", "-", " "]
      for separator in separators:
        if separator in stripped:
          return sorted({part.strip() for part in stripped.split(separator) if part.strip()})
      return [stripped]
  return []


def _coerce_structure(value: Any) -> CrystalStructure | None:
  if value is None:
    return None
  if isinstance(value, CrystalStructure):
    return value
  if isinstance(value, str):
    stripped = value.strip()
    if not stripped:
      return None
    value = json.loads(stripped)
  if isinstance(value, dict):
    return CrystalStructure.model_validate(value)
  return None


def _value_counts(series: pd.Series | None) -> dict[str, int]:
  if series is None:
    return {}
  counts: Counter[str] = Counter()
  for value in series.tolist():
    if _is_missing(value):
      continue
    counts[str(value)] += 1
  return dict(sorted(counts.items()))


def _missing_structure_count(frame: pd.DataFrame) -> int:
  return int(frame["structure"].apply(lambda value: not isinstance(value, CrystalStructure)).sum())


def _mixed_functionals(frame: pd.DataFrame) -> bool:
  if "functional" not in frame.columns:
    return False
  distinct = {
    str(value)
    for value in frame["functional"].tolist()
    if not _is_missing(value)
  }
  return len(distinct) > 1


def _duplicate_signals(frame: pd.DataFrame) -> dict[str, int]:
  reduced_formulas = frame["reduced_formula"] if "reduced_formula" in frame.columns else frame["formula"]
  return {
    "exact_record_duplicate_count": _exact_record_duplicate_count(frame),
    "formula_multiplicity_count": _collision_count(reduced_formulas.tolist()),
    "immutable_id_collision_count": _collision_count(
      frame["immutable_id"].tolist() if "immutable_id" in frame.columns else []
    ),
    "structure_fingerprint_collision_count": _collision_count(
      frame["structure_fingerprint"].tolist() if "structure_fingerprint" in frame.columns else []
    ),
  }


def _exact_record_duplicate_count(frame: pd.DataFrame) -> int:
  signatures = [
    json.dumps(_json_ready_record(record), sort_keys=True, separators=(",", ":"))
    for record in frame.to_dict(orient="records")
  ]
  return _collision_count(signatures)


def _collision_count(values: list[Any]) -> int:
  counts: Counter[str] = Counter()
  for value in values:
    if _is_missing(value):
      continue
    counts[str(value)] += 1
  return sum(count for count in counts.values() if count > 1)


def _json_ready_record(record: dict[str, Any]) -> dict[str, Any]:
  return {key: _json_ready_value(value) for key, value in record.items()}


def _json_ready_value(value: Any) -> Any:
  if isinstance(value, CrystalStructure):
    return value.to_json_dict()
  if isinstance(value, dict):
    return {key: _json_ready_value(subvalue) for key, subvalue in sorted(value.items())}
  if isinstance(value, (list, tuple)):
    return [_json_ready_value(item) for item in value]
  if isinstance(value, pd.Timestamp):
    return value.isoformat()
  if hasattr(value, "item") and callable(getattr(value, "item")):
    try:
      return value.item()
    except Exception:
      return str(value)
  if _is_missing(value):
    return None
  return value


def _infer_property_columns(frame: pd.DataFrame) -> list[str]:
  property_columns: list[str] = []
  for column in frame.columns:
    if column in _STANDARD_COLUMNS:
      continue
    non_null = frame[column].dropna()
    if non_null.empty:
      continue
    if non_null.map(lambda value: isinstance(value, (int, float, str, bool))).all():
      property_columns.append(column)
  return property_columns


def _property_method_from_row(row: dict[str, Any]) -> PropertyMethod:
  return PropertyMethod.DFT if not _is_missing(row.get("functional")) else PropertyMethod.UNKNOWN


def _coerce_property_value(value: Any) -> float | str | dict[str, Any]:
  if isinstance(value, bool):
    return str(value)
  if isinstance(value, (int, float)):
    return float(value)
  if hasattr(value, "item") and callable(getattr(value, "item")):
    try:
      item = value.item()
      if isinstance(item, (int, float)):
        return float(item)
      return str(item)
    except Exception:
      return str(value)
  if isinstance(value, dict):
    return value
  return str(value)


def _coerce_provenance(value: Any) -> list[ProvenanceRecord]:
  if value is None:
    return []
  if isinstance(value, list):
    records: list[ProvenanceRecord] = []
    for item in value:
      if isinstance(item, ProvenanceRecord):
        records.append(item)
      elif isinstance(item, dict):
        records.append(ProvenanceRecord.model_validate(item))
    return records
  return []


def _is_missing(value: Any) -> bool:
  if value is None:
    return True
  if isinstance(value, str):
    return not value.strip()
  try:
    return bool(pd.isna(value))
  except TypeError:
    return False


__all__ = [
  "CandidateSlice",
  "DeduplicationBasis",
  "GraphExportResult",
  "MatterGraphDataset",
]
