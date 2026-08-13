from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from mattergraph_api.services.demo_service import (
  FIXTURE_DISCLAIMER,
  FIXTURE_RELATIVE_PATH,
  RUN_ID,
  SLICE_NAME,
  TARGET,
  WORKFLOW_VERSION,
  get_demo_dataset,
  get_filtered_demo_dataset,
  graph_summary,
)


class CandidateSliceSummary(BaseModel):
  slice_id: str
  slice_name: str
  target: str
  input_count: int
  output_count: int
  removed_count: int
  filter_steps: list[dict[str, Any]] = Field(default_factory=list)
  report: dict[str, Any] = Field(default_factory=dict)


class GraphPreview(BaseModel):
  material_id: str
  formula: str
  node_count: int
  edge_count: int
  node_feature_shape: list[int]
  edge_feature_shape: list[int]
  global_features: dict[str, float | int]


class GraphExportSummary(BaseModel):
  included_count: int
  excluded_count: int
  previews: list[GraphPreview] = Field(default_factory=list)


class BenchmarkSummary(BaseModel):
  target: str
  row_count: int
  columns: list[str]


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
  fixture_kind: str = "illustrative_schema_fixture"
  disclaimer: str


class LeMaterialDemoWorkflowResponse(BaseModel):
  workflow_id: str
  source_dataset: str
  source_subset: str
  schema_report: dict[str, Any]
  candidate_slice: CandidateSliceSummary
  graph_export: GraphExportSummary
  benchmark: BenchmarkSummary
  benchmark_preview: list[BenchmarkPreviewRow]
  provenance: WorkflowProvenance


def build_lematerial_demo_workflow() -> LeMaterialDemoWorkflowResponse:
  dataset = get_demo_dataset()
  filtered = get_filtered_demo_dataset()
  candidate_slice = filtered.create_slice(SLICE_NAME, target=TARGET)
  slice_report = candidate_slice.report()
  graph_export = filtered.to_graphs()
  benchmark_frame = filtered.to_benchmark_frame(target=TARGET)
  store = filtered.to_material_store()
  graph_previews = []
  for material in store.materials:
    if material.structure is None:
      continue
    summary = graph_summary(material)
    graph_previews.append(
      GraphPreview(
        material_id=material.material_id,
        formula=material.formula,
        node_count=len(summary["nodes"]),
        edge_count=summary["edge_count"],
        node_feature_shape=summary["node_feature_shape"],
        edge_feature_shape=summary["edge_feature_shape"],
        global_features=summary["global_features"],
      )
    )

  return LeMaterialDemoWorkflowResponse(
    workflow_id="lematerial_bulk_demo",
    source_dataset=dataset.source_dataset,
    source_subset=dataset.source_subset or "",
    schema_report=dataset.schema_report(),
    candidate_slice=CandidateSliceSummary(
      slice_id=candidate_slice.slice_id,
      slice_name=candidate_slice.slice_name,
      target=candidate_slice.target or TARGET,
      input_count=candidate_slice.input_count,
      output_count=candidate_slice.output_count,
      removed_count=slice_report["removed_count"],
      filter_steps=slice_report["filter_steps"],
      report=slice_report,
    ),
    graph_export=GraphExportSummary(
      included_count=graph_export.included_count,
      excluded_count=graph_export.excluded_count,
      previews=graph_previews,
    ),
    benchmark=BenchmarkSummary(
      target=TARGET,
      row_count=len(benchmark_frame),
      columns=[str(column) for column in benchmark_frame.columns],
    ),
    benchmark_preview=_benchmark_preview(benchmark_frame.to_dict(orient="records")),
    provenance=WorkflowProvenance(
      fixture_path=FIXTURE_RELATIVE_PATH,
      loader="LeMatBulk.from_records",
      workflow_version=WORKFLOW_VERSION,
      run_id=RUN_ID,
      disclaimer=FIXTURE_DISCLAIMER,
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
