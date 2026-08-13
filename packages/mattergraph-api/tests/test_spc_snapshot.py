from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest
from pymatgen.core import Lattice, Structure

EXPECTED_IDS = [
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


def _artifact() -> dict:
  root = Path(__file__).resolve().parents[3]
  return json.loads((root / "data/demo/spc_real_snapshot.json").read_text())


def test_snapshot_membership_checksum_provenance_and_force_contract() -> None:
  artifact = _artifact()
  manifest = artifact["manifest"]
  records = artifact["records"]
  canonical = json.dumps(
    records, sort_keys=True, separators=(",", ":"), allow_nan=False
  ).encode()

  assert manifest["dataset"] == "LeMaterial/LeMat-Bulk"
  assert manifest["subset"] == "compatible_pbe"
  assert manifest["license"] == "CC-BY-4.0"
  assert manifest["citation_doi"] == "10.57967/hf/3762"
  assert manifest["snapshot_count"] == len(records) == 24
  assert [record["immutable_id"] for record in records] == EXPECTED_IDS
  assert hashlib.sha256(canonical).hexdigest() == manifest["snapshot_sha256"]
  assert len({record["structure_fingerprint"] for record in records}) == 24

  for record in records:
    assert "N" in record["elements"]
    assert record["nsites"] <= 16
    assert record["material_id"] == record["immutable_id"]
    forces = record["forces"]
    assert len(forces) == record["nsites"]
    assert all(
      len(vector) == 3
      and all(
        isinstance(value, (int, float)) and math.isfinite(value) for value in vector
      )
      for vector in forces
    )
    structure = Structure(
      Lattice(record["structure"]["lattice"]),
      record["structure"]["species"],
      record["structure"]["coords"],
    )
    assert structure.is_ordered
    assert float(structure.density) == pytest.approx(record["density"], rel=1e-10)
    assert record["field_provenance"]["energy_above_hull"].startswith(
      "LeMaterial/LeMat-Bulk-DFT-Hull-All@"
    )


def test_chgnet_reference_input_checksum_matches_selected_record() -> None:
  artifact = _artifact()
  root = Path(__file__).resolve().parents[3]
  reference = json.loads((root / "data/demo/chgnet_reference.json").read_text())
  record = next(
    row for row in artifact["records"] if row["material_id"] == reference["material_id"]
  )
  canonical = json.dumps(
    record["structure"], sort_keys=True, separators=(",", ":"), allow_nan=False
  ).encode()
  assert hashlib.sha256(canonical).hexdigest() == reference["input_checksum"]
  assert reference["model"]["weight_checksum"] == (
    "d14ab7c0f093efe64b60a7bcd540bca10e74fb7f46c86108a079af60524659d1"
  )
  assert reference["model"]["version"] == "0.3.0"
  assert reference["label"] == "cached_reference"
