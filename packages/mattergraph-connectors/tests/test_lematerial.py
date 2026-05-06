from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest
from mattergraph_connectors.lematerial import LeMatBulk


def _load_records() -> list[dict[str, object]]:
  root = Path(__file__).resolve().parents[3]
  path = root / "data" / "demo" / "lemat_bulk_sample.json"
  return json.loads(path.read_text())


def test_lemat_bulk_from_records_report_and_graph_guardrail_surface() -> None:
  dataset = LeMatBulk.from_records(_load_records(), subset="compatible_pbesol")
  filtered = dataset.candidate_pool(include=["Al", "N", "Ti"], max_nsites=4, max_nelements=3)
  candidate_slice = filtered.create_slice("marine_pressure_candidates_v0", target="bulk_modulus")

  report = candidate_slice.report()

  assert report["slice_id"].startswith("mg_slice_")
  assert report["source_subset"] == "compatible_pbesol"
  assert report["duplicate_policy"] == "disallow_duplicate_records"
  assert report["deduplication_basis"] == "structure_fingerprint"
  assert report["duplicate_signals"]["formula_multiplicity_count"] == 2
  assert report["missing_structure_count"] == 1
  assert report["graph_export_excluded_count"] == 0


def test_repeated_formula_polymorphs_do_not_fail_by_default() -> None:
  dataset = LeMatBulk.from_records(_load_records(), subset="compatible_pbesol")
  candidate_slice = dataset.create_slice("polymorph_safe")

  assert candidate_slice.report()["output_count"] == 4


def test_mixed_functionals_fail_without_override() -> None:
  records = deepcopy(_load_records())
  records[1]["functional"] = "PBE"
  dataset = LeMatBulk.from_records(records, subset="compatible_bulk")

  with pytest.raises(ValueError, match="Mixed functionals"):
    dataset.create_slice("mixed_functionals")

  allowed = dataset.create_slice("mixed_functionals", allow_mixed_functionals=True)
  assert allowed.report()["mixed_functionals"] is True


def test_immutable_id_collisions_fail_unless_explicitly_allowed() -> None:
  records = deepcopy(_load_records())
  records[1]["immutable_id"] = records[0]["immutable_id"]
  records[1]["structure_fingerprint"] = "lemat-fp-999"
  dataset = LeMatBulk.from_records(records, subset="bulk_unique")

  with pytest.raises(ValueError, match="Immutable-id collisions"):
    dataset.create_slice("immutable_collision")

  assert dataset.create_slice("immutable_collision", allow_duplicate_records=True)


def test_structure_fingerprint_collisions_fail_unless_explicitly_allowed() -> None:
  records = deepcopy(_load_records())
  records[1]["structure_fingerprint"] = records[0]["structure_fingerprint"]
  dataset = LeMatBulk.from_records(records, subset="compatible_pbesol")

  with pytest.raises(ValueError, match="Structure-fingerprint collisions"):
    dataset.create_slice("fingerprint_collision")

  assert dataset.create_slice("fingerprint_collision", allow_duplicate_records=True)


def test_exact_repeated_records_fail_unless_explicitly_allowed() -> None:
  records = deepcopy(_load_records())
  records.append(deepcopy(records[0]))
  dataset = LeMatBulk.from_records(records, subset="compatible_pbesol")

  with pytest.raises(ValueError, match="Exact repeated records"):
    dataset.create_slice("exact_duplicates")

  assert dataset.create_slice("exact_duplicates", allow_duplicate_records=True)


def test_formula_only_deduplication_is_explicit() -> None:
  dataset = LeMatBulk.from_records(_load_records(), subset="compatible_pbesol")

  with pytest.raises(ValueError, match="Formula-only duplicate handling"):
    dataset.create_slice("formula_only", deduplication_basis="formula_only")


def test_unknown_deduplication_basis_blocks_duplicate_sensitive_slices() -> None:
  records = deepcopy(_load_records())
  for record in records:
    record.pop("structure_fingerprint", None)
    record.pop("immutable_id", None)
  dataset = LeMatBulk.from_records(records, subset="compatible_pbesol")

  with pytest.raises(ValueError, match="deduplication basis is unknown"):
    dataset.create_slice("unknown_basis")

  assert dataset.create_slice("unknown_basis", allow_duplicate_records=True)


def test_from_parquet_uses_pandas_loader(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
  frame = pd.DataFrame(_load_records())

  def fake_read_parquet(path: Path) -> pd.DataFrame:
    assert path == tmp_path / "bulk.parquet"
    return frame

  monkeypatch.setattr(pd, "read_parquet", fake_read_parquet)

  dataset = LeMatBulk.from_parquet(tmp_path / "bulk.parquet", subset="compatible_pbesol")
  assert dataset.schema_report()["row_count"] == 4
