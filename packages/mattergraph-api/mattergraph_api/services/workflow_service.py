from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mattergraph_connectors import LeMatBulk
from pydantic import BaseModel, Field

_FIXTURE_RELATIVE_PATH = "data/demo/lemat_bulk_sample.json"
_SOURCE_DATASET = "LeMaterial/LeMat-Bulk"
_SOURCE_SUBSET = "compatible_pbesol"
_SLICE_NAME = "marine_pressure_candidates_v0"
_TARGET = "bulk_modulus"


class CandidateSliceSummary(BaseModel):
  slice_id: str
  slice_name: str
  target: str
  input_count: int
  output_count: int
  removed_count: int
  filter_steps: list[dict[str, Any]] = Field(default_factory=list)


class GraphExportSummary(BaseModel):
  included_count: int
  excluded_count: int


class BenchmarkPreviewRow(BaseModel):
  material_id: str
  formula: str
  target: float | str | None
  density: float | str | None = None
  bulk_modulus: float | str | None = None
  energy_above_hull: float | str | None = None
  nsites: int | None = None
  nelements: int | None = None


class WorkflowProvenance(BaseModel):
  fixture_path: str
  loader: str
  workflow_version: str
  run_id: str


class LeMaterialDemoWorkflowResponse(BaseModel):
  workflow_id: str
  source_dataset: str
  source_subset: str
  schema_report: dict[str, Any]
  candidate_slice: CandidateSliceSummary
  graph_export: GraphExportSummary
  benchmark_preview: list[BenchmarkPreviewRow]
  provenance: WorkflowProvenance


def build_lematerial_demo_workflow() -> LeMaterialDemoWorkflowResponse:
  fixture_path = _repo_root() / _FIXTURE_RELATIVE_PATH
  records = json.loads(fixture_path.read_text())
  dataset = LeMatBulk.from_records(
    records,
    source_dataset=_SOURCE_DATASET,
    subset=_SOURCE_SUBSET,
  )
  filtered = dataset.filter_elements(include=["Ti", "Al", "N"]).filter_complexity(
    max_nsites=4,
    max_nelements=3,
  )
  candidate_slice = filtered.create_slice(_SLICE_NAME, target=_TARGET)
  slice_report = candidate_slice.report()
  graph_export = filtered.to_graphs()
  benchmark_frame = filtered.to_benchmark_frame(target=_TARGET)

  return LeMaterialDemoWorkflowResponse(
    workflow_id="lematerial_bulk_demo",
    source_dataset=dataset.source_dataset,
    source_subset=dataset.source_subset or "",
    schema_report=dataset.schema_report(),
    candidate_slice=CandidateSliceSummary(
      slice_id=candidate_slice.slice_id,
      slice_name=candidate_slice.slice_name,
      target=candidate_slice.target or _TARGET,
      input_count=candidate_slice.input_count,
      output_count=candidate_slice.output_count,
      removed_count=slice_report["removed_count"],
      filter_steps=slice_report["filter_steps"],
    ),
    graph_export=GraphExportSummary(
      included_count=graph_export.included_count,
      excluded_count=graph_export.excluded_count,
    ),
    benchmark_preview=_benchmark_preview(benchmark_frame.to_dict(orient="records")),
    provenance=WorkflowProvenance(
      fixture_path=_FIXTURE_RELATIVE_PATH,
      loader="LeMatBulk.from_records",
      workflow_version="v0.1",
      run_id="lematerial_bulk_demo_static_v0_1",
    ),
  )


def _benchmark_preview(records: list[dict[str, Any]]) -> list[BenchmarkPreviewRow]:
  preview: list[BenchmarkPreviewRow] = []
  for row in records[:3]:
    preview.append(
      BenchmarkPreviewRow(
        material_id=str(row["material_id"]),
        formula=str(row["formula"]),
        target=_json_scalar(row.get("target")),
        density=_json_scalar(row.get("density")),
        bulk_modulus=_json_scalar(row.get("bulk_modulus")),
        energy_above_hull=_json_scalar(row.get("energy_above_hull")),
        nsites=_json_int(row.get("nsites")),
        nelements=_json_int(row.get("nelements")),
      )
    )
  return preview


def _json_scalar(value: Any) -> float | str | None:
  if value is None:
    return None
  if hasattr(value, "item") and callable(value.item):
    value = value.item()
  if isinstance(value, (int, float)):
    return float(value)
  if isinstance(value, str):
    return value
  return str(value)


def _json_int(value: Any) -> int | None:
  if value is None:
    return None
  if hasattr(value, "item") and callable(value.item):
    value = value.item()
  return int(value)


def _repo_root() -> Path:
  return Path(__file__).resolve().parents[4]
