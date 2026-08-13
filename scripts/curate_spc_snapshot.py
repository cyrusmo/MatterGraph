#!/usr/bin/env python3
"""Curate the frozen, offline SPC demo cohort from public LeMaterial data.

The checked-in artifact is intentionally small. This script records the exact upstream
revisions, reconstructs every structure, enforces the force-shape contract, joins DFT hull
values by immutable ID, and hashes the canonical records payload. DuckDB is an optional
curation-only dependency; it is not required to run the demo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from pymatgen.core import Composition, Lattice, Structure

BASE_DATASET = "LeMaterial/LeMat-Bulk"
BASE_SUBSET = "compatible_pbe"
BASE_REVISION = "0dc17eea904b860ad7288141e9870f67f8e6bb2c"
HULL_DATASET = "LeMaterial/LeMat-Bulk-DFT-Hull-All"
HULL_REVISION = "fc063a965498df6481911bdfdb3cad5619016d81"
LICENSE = "CC-BY-4.0"
CITATION_DOI = "10.57967/hf/3762"
SOURCE_POPULATION = 5_335_299
SNAPSHOT_SIZE = 24
BASE_SHARD_COUNT = 3

BASE_URL = (
  "https://huggingface.co/datasets/LeMaterial/LeMat-Bulk/resolve/"
  f"{BASE_REVISION}/compatible_pbe/train-{{shard:05d}}-of-00017.parquet"
)
HULL_URL = (
  "https://huggingface.co/datasets/LeMaterial/LeMat-Bulk-DFT-Hull-All/resolve/"
  f"{HULL_REVISION}/data/train-{{shard:05d}}-of-00002.parquet"
)

BASE_COLUMNS = (
  "elements, nsites, chemical_formula_reduced, nelements, lattice_vectors, immutable_id, "
  "cartesian_site_positions, species_at_sites, last_modified, energy, forces, functional, "
  "entalpic_fingerprint"
)


def _duckdb() -> Any:
  try:
    import duckdb
  except ImportError as exc:  # pragma: no cover - only used by maintainers
    msg = "Install the curation-only dependency with `pip install duckdb`."
    raise SystemExit(msg) from exc
  connection = duckdb.connect()
  connection.execute("SET enable_progress_bar=false")
  connection.execute("SET allow_asterisks_in_http_paths=true")
  return connection


def _resolved_url(url: str) -> str:
  """Resolve a Hub file once so DuckDB range reads hit the signed CDN directly."""
  request = Request(url, method="HEAD", headers={"User-Agent": "mattergraph-curator/1"})
  with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed public dataset URLs
    return response.geturl()


def _base_rows(connection: Any) -> list[dict[str, Any]]:
  urls = [_resolved_url(BASE_URL.format(shard=index)) for index in range(BASE_SHARD_COUNT)]
  records: list[dict[str, Any]] = []
  for url in urls:
    cursor = connection.execute(
      f"""
        SELECT {BASE_COLUMNS}
        FROM read_parquet(?)
        WHERE list_has_all(['Ti', 'Al', 'N'], elements)
          AND list_contains(elements, 'N')
          AND (list_contains(elements, 'Ti') OR list_contains(elements, 'Al'))
          AND nelements BETWEEN 2 AND 3
          AND nsites <= 16
          AND nperiodic_dimensions = 3
        ORDER BY immutable_id
      """,
      [url],
    )
    names = [item[0] for item in cursor.description]
    records.extend(dict(zip(names, row, strict=True)) for row in cursor.fetchall())
  return records


def _hull_values(connection: Any, immutable_ids: list[str]) -> dict[str, float]:
  if not immutable_ids:
    return {}
  urls = [_resolved_url(HULL_URL.format(shard=index)) for index in range(2)]
  id_placeholders = ", ".join("?" for _ in immutable_ids)
  values: dict[str, float] = {}
  for url in urls:
    query = f"""
      SELECT immutable_id, dft_hull
      FROM read_parquet(?)
      WHERE immutable_id IN ({id_placeholders})
        AND isfinite(dft_hull)
    """
    values.update(
      {
        str(immutable_id): float(value)
        for immutable_id, value in connection.execute(
          query, [url, *immutable_ids]
        ).fetchall()
      }
    )
  return values


def _valid_forces(forces: Any, nsites: int) -> bool:
  return (
    isinstance(forces, list)
    and len(forces) == nsites
    and all(
      isinstance(vector, list)
      and len(vector) == 3
      and all(isinstance(value, (int, float)) and math.isfinite(value) for value in vector)
      for vector in forces
    )
  )


def _max_force(forces: list[list[float]]) -> float:
  return max(math.sqrt(sum(float(value) ** 2 for value in vector)) for vector in forces)


def _candidate(row: dict[str, Any], hull: float) -> dict[str, Any] | None:
  nsites = int(row["nsites"])
  forces = row["forces"]
  fingerprint = str(row.get("entalpic_fingerprint") or "").strip()
  if not fingerprint or not _valid_forces(forces, nsites):
    return None
  try:
    structure = Structure(
      Lattice(row["lattice_vectors"]),
      row["species_at_sites"],
      row["cartesian_site_positions"],
      coords_are_cartesian=True,
      to_unit_cell=True,
    )
  except (TypeError, ValueError):
    return None
  if len(structure) != nsites or not structure.is_ordered:
    return None

  material_id = str(row["immutable_id"])
  source_formula = str(row["chemical_formula_reduced"])
  formula = Composition(source_formula).reduced_formula
  max_force = _max_force(forces)
  return {
    "material_id": material_id,
    "immutable_id": material_id,
    "formula": formula,
    "reduced_formula": formula,
    "source_reduced_formula": source_formula,
    "elements": sorted(str(element) for element in row["elements"]),
    "nelements": int(row["nelements"]),
    "nsites": nsites,
    "functional": str(row["functional"]),
    "structure_fingerprint": fingerprint,
    "structure": {
      "lattice": [[float(value) for value in vector] for vector in structure.lattice.matrix],
      "species": [str(site.specie) for site in structure],
      "coords": [[float(value) for value in site.frac_coords] for site in structure],
      "site_properties": None,
    },
    "density": float(structure.density),
    "energy_above_hull": float(hull),
    "max_force": float(max_force),
    "energy": float(row["energy"]),
    "forces": [[float(value) for value in vector] for vector in forces],
    "last_modified": str(row["last_modified"]),
    "provenance": [
      {
        "source": BASE_DATASET,
        "method": "dft",
        "source_id": material_id,
        "notes": "Structure, energy, force, and functional fields from compatible_pbe.",
        "parameters": {"subset": BASE_SUBSET, "revision": BASE_REVISION},
      },
      {
        "source": HULL_DATASET,
        "method": "dft",
        "source_id": material_id,
        "notes": "DFT energy above hull joined on immutable_id.",
        "parameters": {"revision": HULL_REVISION},
      },
      {
        "source": "MatterGraph",
        "method": "derived",
        "source_id": material_id,
        "notes": "Density reconstructed from lattice/species; max_force is the largest force norm.",
        "parameters": {"curation_schema": "spc-demo-snapshot-v1"},
      },
    ],
    "field_provenance": {
      "structure": f"{BASE_DATASET}/{BASE_SUBSET}@{BASE_REVISION}",
      "forces": f"{BASE_DATASET}/{BASE_SUBSET}@{BASE_REVISION}",
      "energy": f"{BASE_DATASET}/{BASE_SUBSET}@{BASE_REVISION}",
      "functional": f"{BASE_DATASET}/{BASE_SUBSET}@{BASE_REVISION}",
      "structure_fingerprint": f"{BASE_DATASET}/{BASE_SUBSET}@{BASE_REVISION}",
      "energy_above_hull": f"{HULL_DATASET}@{HULL_REVISION}",
      "density": "MatterGraph:pymatgen.Structure.density",
      "max_force": "MatterGraph:max(||force_i||)",
    },
  }


def _select(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
  unique: dict[str, dict[str, Any]] = {}
  for candidate in candidates:
    unique.setdefault(candidate["structure_fingerprint"], candidate)
  values = list(unique.values())
  values.sort(
    key=lambda row: (
      row["energy_above_hull"] > 0.05,
      row["max_force"] > 0.2,
      row["energy_above_hull"],
      row["density"],
      row["material_id"],
    )
  )
  groups = {
    "al_n": [row for row in values if "Al" in row["elements"] and "Ti" not in row["elements"]],
    "ti_n": [row for row in values if "Ti" in row["elements"] and "Al" not in row["elements"]],
    "ti_al_n": [row for row in values if {"Ti", "Al", "N"}.issubset(row["elements"])],
  }
  selected = [row for group in groups.values() for row in group[:8]]
  selected.sort(key=lambda row: row["material_id"])
  if len(selected) != SNAPSHOT_SIZE:
    msg = f"curation contract requires {SNAPSHOT_SIZE} records; found {len(selected)}"
    raise SystemExit(msg)
  group_counts = Counter(
    "ternary" if len(row["elements"]) == 3 else row["formula"] for row in selected
  )
  if any(len(group) < 8 for group in groups.values()):
    msg = f"cohort requires 8 Al-N, 8 Ti-N, and 8 Ti-Al-N rows; found {dict(group_counts)}"
    raise SystemExit(msg)
  eligible = sum(
    row["energy_above_hull"] <= 0.05 and row["max_force"] <= 0.2 for row in selected
  )
  if eligible < 3:
    raise SystemExit(f"cohort requires at least 3 scorecard-eligible rows; found {eligible}")
  return selected


def _canonical_bytes(records: list[dict[str, Any]]) -> bytes:
  return json.dumps(records, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def curate(output: Path) -> None:
  connection = _duckdb()
  source_rows = _base_rows(connection)
  hull_by_id = _hull_values(connection, [str(row["immutable_id"]) for row in source_rows])
  candidates = [
    candidate
    for row in source_rows
    if (hull := hull_by_id.get(str(row["immutable_id"]))) is not None
    if (candidate := _candidate(row, hull)) is not None
  ]
  records = _select(candidates)
  checksum = hashlib.sha256(_canonical_bytes(records)).hexdigest()
  output.parent.mkdir(parents=True, exist_ok=True)
  artifact = {
    "manifest": {
      "schema_version": "spc-demo-snapshot-v1",
      "created_at": datetime.now(timezone.utc).isoformat(),
      "dataset": BASE_DATASET,
      "subset": BASE_SUBSET,
      "upstream_revision": BASE_REVISION,
      "hull_dataset": HULL_DATASET,
      "hull_revision": HULL_REVISION,
      "license": LICENSE,
      "citation_doi": CITATION_DOI,
      "source_population": SOURCE_POPULATION,
      "snapshot_count": len(records),
      "snapshot_sha256": checksum,
      "checksum_scope": "SHA-256 of canonical JSON records array",
      "selection": {
        "chemistry": "8 Al-N + 8 Ti-N + 8 Ti-Al-N records; formulas canonicalized by pymatgen",
        "required_elements": ["N"],
        "max_sites": 16,
        "ordered_only": True,
        "unique_by": "entalpic_fingerprint",
        "valid_forces": "one finite numeric 3-vector per site",
        "base_shards_scanned": BASE_SHARD_COUNT,
      },
      "field_sources": {
        "structure": "LeMat-Bulk lattice_vectors + cartesian_site_positions + species_at_sites",
        "forces": "LeMat-Bulk forces",
        "energy": "LeMat-Bulk energy",
        "fingerprint": "LeMat-Bulk entalpic_fingerprint",
        "energy_above_hull": "LeMat-Bulk-DFT-Hull-All dft_hull",
        "density": "derived from reconstructed pymatgen Structure",
        "max_force": "derived maximum Euclidean norm of forces",
      },
    },
    "records": records,
  }
  output.write_text(json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n")
  eligible = sum(
    row["energy_above_hull"] <= 0.05 and row["max_force"] <= 0.2 for row in records
  )
  print(
    f"wrote {len(records)} records ({eligible} constraint-eligible) to {output}; sha256={checksum}"
  )


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument(
    "--output",
    type=Path,
    default=Path("data/demo/spc_real_snapshot.json"),
  )
  arguments = parser.parse_args()
  curate(arguments.output)


if __name__ == "__main__":
  main()
