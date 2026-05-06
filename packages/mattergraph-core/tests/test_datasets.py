from __future__ import annotations

import json
from pathlib import Path

from mattergraph.datasets import MatterGraphDataset


def _load_records() -> list[dict[str, object]]:
  root = Path(__file__).resolve().parents[3]
  path = root / "data" / "demo" / "lemat_bulk_sample.json"
  return json.loads(path.read_text())


def test_dataset_filters_are_immutable_and_report_steps() -> None:
  dataset = MatterGraphDataset.from_records(
    _load_records(),
    source_dataset="demo/lematerial",
    source_subset="fixture",
  )

  filtered = dataset.filter_elements(include=["Ti", "Al", "N"]).filter_complexity(max_nsites=3)
  first_slice = filtered.create_slice("fixture_slice")
  second_slice = filtered.create_slice("fixture_slice")

  assert len(dataset) == 4
  assert len(filtered) == 3
  assert first_slice.slice_id == second_slice.slice_id
  report = first_slice.report()
  assert report["columns_used"] == ["elements", "nsites"]
  assert [step["name"] for step in report["filter_steps"]] == [
    "filter_elements",
    "filter_complexity",
  ]
  assert report["filter_steps"][0]["input_count"] == 4
  assert report["filter_steps"][1]["output_count"] == 3


def test_dataset_schema_report_and_element_counts() -> None:
  dataset = MatterGraphDataset.from_records(
    _load_records(),
    source_dataset="demo/lematerial",
    source_subset="fixture",
  )

  report = dataset.schema_report()
  counts = dataset.element_counts()

  assert report["row_count"] == 4
  assert report["missing_structure_count"] == 1
  assert report["duplicate_signals"]["formula_multiplicity_count"] == 2
  assert not report["mixed_functionals"]
  assert counts["N"] == 4
  assert counts["Ti"] == 3


def test_dataset_material_store_graph_export_and_benchmark_frame() -> None:
  dataset = MatterGraphDataset.from_records(
    _load_records(),
    source_dataset="demo/lematerial",
    source_subset="fixture",
  )

  store = dataset.to_material_store()
  graph_result = dataset.to_graphs()
  benchmark_frame = dataset.to_benchmark_frame(target="bulk_modulus")

  assert len(store.materials) == 4
  assert graph_result.included_count == 3
  assert graph_result.excluded_count == 1
  assert graph_result.graphs[0]["graph"].num_atoms >= 2
  assert "target" in benchmark_frame.columns
  assert benchmark_frame["source_dataset"].iloc[0] == "demo/lematerial"
