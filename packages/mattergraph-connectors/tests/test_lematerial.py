from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from pathlib import Path

import pandas as pd
import pytest
from mattergraph_connectors.lematerial import LeMatBulk

EXPECTED_EXAMPLE_IDS = [
  "agm002163329",
  "agm002164077",
  "agm002164923",
  "agm002346334",
  "agm002858657",
  "agm003220445",
  "agm003273599",
  "agm003319993",
  "agm003492481",
  "agm003707212",
  "agm004462264",
  "agm004462854",
  "agm005543670",
  "agm005708132",
  "agm005779324",
  "agm005909527",
  "agm006182041",
  "agm2000002653",
  "agm2000006184",
  "agm2000008813",
  "agm2000021145",
  "agm2000110212",
  "mp-13178",
  "mp-1330",
]


def _load_records() -> list[dict[str, object]]:
  root = Path(__file__).resolve().parents[3]
  path = root / "data" / "demo" / "lemat_bulk_sample.json"
  return json.loads(path.read_text())


def test_packaged_example_is_attributed_graph_ready_and_cwd_independent(
  monkeypatch: pytest.MonkeyPatch,
  tmp_path: Path,
) -> None:
  monkeypatch.chdir(tmp_path)
  dataset = LeMatBulk.example()
  manifest = dataset.metadata["snapshot_manifest"]

  assert dataset.metadata["example_name"] == "spc-tialn-24"
  assert dataset.schema_report()["row_count"] == 24
  assert dataset.to_pandas()["immutable_id"].tolist() == EXPECTED_EXAMPLE_IDS
  assert manifest["dataset"] == "LeMaterial/LeMat-Bulk"
  assert manifest["subset"] == "compatible_pbe"
  assert manifest["license"] == "CC-BY-4.0"
  assert manifest["citation_doi"] == "10.57967/hf/3762"
  assert manifest["upstream_revision"] == "0dc17eea904b860ad7288141e9870f67f8e6bb2c"
  assert manifest["hull_revision"] == "fc063a965498df6481911bdfdb3cad5619016d81"
  assert manifest["snapshot_sha256"] == (
    "e1a925b5b047b9fc3d4172b7647c23de656f7422e990234c343dcbb9fa333c14"
  )

  graphs = dataset.to_graphs()
  assert graphs.included_count == 24
  assert graphs.excluded_count == 0


def test_packaged_example_resource_matches_canonical_snapshot() -> None:
  root = Path(__file__).resolve().parents[3]
  packaged = (
    files("mattergraph_connectors")
    .joinpath("resources", "spc_real_snapshot.json")
    .read_bytes()
  )
  assert packaged == (root / "data/demo/spc_real_snapshot.json").read_bytes()


def test_packaged_example_rejects_unknown_name() -> None:
  with pytest.raises(ValueError, match="available examples: spc-tialn-24"):
    LeMatBulk.example("not-a-real-example")


def test_lemat_bulk_from_records_report_and_graph_guardrail_surface() -> None:
  dataset = LeMatBulk.from_records(_load_records(), subset="compatible_pbesol")
  filtered = dataset.candidate_pool(include=["Al", "N", "Ti"], max_nsites=4, max_nelements=3)
  candidate_slice = filtered.create_slice("bulk_modulus_candidates_v0", target="bulk_modulus")

  report = candidate_slice.report()

  assert report["slice_id"].startswith("mg_slice_")
  assert report["source_subset"] == "compatible_pbesol"
  assert report["duplicate_policy"] == "disallow_duplicate_records"
  assert report["deduplication_basis"] == "structure_fingerprint"
  assert report["duplicate_signals"]["formula_multiplicity_count"] == 2
  assert report["missing_structure_count"] == 1
  assert report["graph_export_excluded_count"] == 0

  materials = dataset.to_material_store().materials
  assert materials[0].get_property("density").unit == "g/cm^3"
  assert materials[0].get_property("bulk_modulus").unit == "GPa"
  assert materials[0].get_property("energy_above_hull").unit == "eV/atom"


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
