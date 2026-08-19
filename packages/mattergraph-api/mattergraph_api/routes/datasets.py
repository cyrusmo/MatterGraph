from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Response
from mattergraph import MaterialStore
from mattergraph.datasets import DeduplicationBasis, MatterGraphDataset
from mattergraph_connectors.local_import import (
  DatasetImportMapping,
  ImportReport,
  ImportResult,
  import_local_content,
  inspect_local_content,
)
from pydantic import BaseModel, ConfigDict, Field

from mattergraph_api.services.dataset_registry import dataset_registry
from mattergraph_api.services.demo_service import graph_summary

router = APIRouter(prefix="/datasets")


class InspectRequest(BaseModel):
  model_config = ConfigDict(extra="forbid")

  filename: str
  format: Literal["csv", "jsonl"]
  content: str


class ImportRequest(InspectRequest):
  mapping: DatasetImportMapping | None = None
  error_policy: Literal["reject_file", "skip_invalid_rows"] = "reject_file"


class SlicePreviewRequest(BaseModel):
  model_config = ConfigDict(extra="forbid")

  include_elements: list[str] = Field(default_factory=list)
  exclude_elements: list[str] = Field(default_factory=list)
  max_nsites: int | None = Field(default=None, ge=1)
  max_nelements: int | None = Field(default=None, ge=1)
  target: str | None = None
  deduplication_basis: DeduplicationBasis = "immutable_id"
  allow_mixed_functionals: bool = False
  allow_duplicate_records: bool = False


@router.get("")
def list_datasets() -> dict[str, Any]:
  return {"datasets": dataset_registry.list(), "registry": dataset_registry.stats()}


@router.post("/inspect", response_model=ImportReport)
def inspect_dataset(request: InspectRequest) -> ImportReport:
  return inspect_local_content(
    filename=request.filename,
    format=request.format,
    content=request.content,
  )


@router.post("/import", response_model=ImportResult)
def import_dataset(request: ImportRequest) -> ImportResult:
  imported = import_local_content(
    filename=request.filename,
    format=request.format,
    content=request.content,
    mapping=request.mapping,
    error_policy=request.error_policy,
  )
  dataset_registry.register(
    imported.result.manifest,
    imported.normalized_jsonl,
  )
  return imported.result.model_copy(
    update={
      "manifest": imported.result.manifest.model_copy(
        update={"degraded": imported.result.manifest.degraded}
      )
    }
  )


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str) -> dict[str, Any]:
  return dataset_registry.status(dataset_id)


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str) -> dict[str, Any]:
  manifest = dataset_registry.delete(dataset_id)
  return {"deleted": True, "dataset_id": manifest.dataset_id}


@router.get("/{dataset_id}/export")
def export_dataset(dataset_id: str, format: Literal["jsonl"] = "jsonl") -> Response:
  manifest, payload = dataset_registry.export(dataset_id)
  return Response(
    content=payload,
    media_type="application/x-ndjson",
    headers={
      "Content-Disposition": f'attachment; filename="{manifest.dataset_id}.jsonl"',
      "X-MatterGraph-Dataset-Id": manifest.dataset_id,
      "X-MatterGraph-SHA256": manifest.normalized_sha256,
      "X-MatterGraph-Record-Count": str(manifest.record_count),
    },
  )


@router.post("/{dataset_id}/slices/preview")
def preview_slice(dataset_id: str, request: SlicePreviewRequest) -> dict[str, Any]:
  store = dataset_registry.materialize(dataset_id)
  dataset = _dataset_from_store(dataset_id, store)
  candidate = dataset.candidate_pool(
    include=request.include_elements,
    exclude=request.exclude_elements,
    max_nsites=request.max_nsites,
    max_nelements=request.max_nelements,
  )
  candidate_slice = candidate.create_slice(
    "local_workbench_preview",
    allow_mixed_functionals=request.allow_mixed_functionals,
    allow_duplicate_records=request.allow_duplicate_records,
    deduplication_basis=request.deduplication_basis,
    target=request.target,
  )
  graph_ready = 0
  graph_excluded = 0
  material_ids = [str(value) for value in candidate_slice.frame["material_id"].tolist()]
  materials_by_id = {material.material_id: material for material in store.materials}
  for material_id in material_ids:
    try:
      graph_summary(materials_by_id[material_id], max_edges=0)
      graph_ready += 1
    except ValueError:
      graph_excluded += 1
  preview_columns = ["material_id", "formula", "nsites", "nelements"]
  if request.target:
    preview_columns.append(request.target)
  frame = candidate_slice.frame
  preview_columns = [column for column in preview_columns if column in frame.columns]
  benchmark_preview = frame[preview_columns].head(20).where(frame.notna(), None).to_dict(
    orient="records"
  )
  return {
    "slice": candidate_slice.report(),
    "material_ids": material_ids,
    "graph_readiness": {"included_count": graph_ready, "excluded_count": graph_excluded},
    "benchmark_preview": benchmark_preview,
  }


def _dataset_from_store(dataset_id: str, store: MaterialStore) -> MatterGraphDataset:
  records: list[dict[str, Any]] = []
  property_columns: set[str] = set()
  property_units: dict[str, str] = {}
  for material in store.materials:
    record: dict[str, Any] = {
      "material_id": material.material_id,
      "formula": material.formula,
      "reduced_formula": material.reduced_formula,
      "elements": material.elements,
      "structure": material.structure,
      "immutable_id": material.material_id,
      "provenance": material.provenance,
    }
    for property_value in material.properties:
      record[property_value.name] = property_value.value
      property_columns.add(property_value.name)
      if property_value.unit:
        property_units.setdefault(property_value.name, property_value.unit)
    records.append(record)
  return MatterGraphDataset.from_records(
    records,
    source_dataset=dataset_id,
    source_subset="local_import",
    metadata={
      "default_deduplication_basis": "immutable_id",
      "property_columns": sorted(property_columns),
      "property_units": property_units,
      "provenance_fields": ["immutable_id", "provenance"],
    },
  )
