from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from typing import Any, Iterable

import numpy as np
from pydantic import BaseModel, ConfigDict

from mattergraph.navigator.registry import canonical_digest, canonical_json

INDEX_SEED = "mattergraph-navigator-index-v1"
UPSTREAM_REVISION = "0dc17eea904b860ad7288141e9870f67f8e6bb2c"


class FrozenIndex(BaseModel):
  model_config = ConfigDict(extra="forbid")

  records: list[dict[str, Any]]
  manifest: dict[str, Any]


def freeze_index(
  records: Iterable[dict[str, Any]],
  *,
  target_count: int = 25_000,
  source_hashes: dict[str, str] | None = None,
) -> FrozenIndex:
  """Mechanically select a capacity-safe, stratified index from compatible PBE records."""
  if target_count <= 0:
    raise ValueError("target_count must be positive")
  source_records = list(records)
  eligible, exclusions = _eligible_records(source_records)
  deduplicated, duplicate_report = _deduplicate(eligible)
  if len(deduplicated) < target_count:
    raise ValueError(
      f"eligible population {len(deduplicated)} is below requested target {target_count}"
    )

  strata: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for record in deduplicated:
    strata[_stratum_key(record)].append(record)
  populations = {key: len(value) for key, value in strata.items()}
  quotas, initial_quotas, redistributions = _allocate_quotas(populations, target_count)

  selected: list[dict[str, Any]] = []
  for key in sorted(strata):
    ordered = sorted(
      strata[key],
      key=lambda item: _selection_hash(str(item["immutable_id"])),
    )
    selected.extend(ordered[:quotas[key]])
  selected.sort(key=lambda item: str(item["immutable_id"]))
  selected_ids = [str(item["immutable_id"]) for item in selected]
  manifest_body: dict[str, Any] = {
    "schema_version": "mattergraph-navigator-index-manifest-v1",
    "index_id": "index_v1",
    "dataset": "LeMaterial/LeMat-Bulk",
    "subset": "compatible_pbe",
    "upstream_revision": UPSTREAM_REVISION,
    "selection_seed": INDEX_SEED,
    "selection_hash_contract": "sha256(canonical_json([seed, immutable_id]))",
    "target_count": target_count,
    "input_count": len(source_records),
    "eligible_count_before_deduplication": len(eligible),
    "eligible_count": len(deduplicated),
    "exclusions": exclusions,
    "duplicates": duplicate_report,
    "source_hashes": source_hashes or {},
    "derivation_versions": {
      "atomic_mass_table": "mattergraph-atomic-masses-v1",
      "density": "density-from-structure-v1",
      "maximum_force_norm": "maximum-force-norm-v1",
      "absolute_total_magnetization": "absolute-total-magnetization-v1",
      "absolute_total_magnetization_per_site": (
        "absolute-total-magnetization-per-site-v1"
      ),
      "maximum_absolute_reported_site_moment": "maximum-absolute-site-moment-v1",
    },
    "strata": {
      key: {
        "population": populations[key],
        "initial_quota": initial_quotas[key],
        "final_quota": quotas[key],
      }
      for key in sorted(strata)
    },
    "redistributions": redistributions,
    "selected_ids": selected_ids,
    "coverage": _coverage(selected),
  }
  manifest_body["manifest_sha256"] = canonical_digest(manifest_body)
  return FrozenIndex(records=selected, manifest=manifest_body)


def _eligible_records(
  records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
  eligible: list[dict[str, Any]] = []
  excluded: dict[str, int] = defaultdict(int)
  for record in records:
    identifier = str(record.get("immutable_id") or "").strip()
    if not identifier:
      excluded["missing_immutable_id"] += 1
      continue
    if not str(
      record.get("formula")
      or record.get("reduced_formula")
      or record.get("chemical_formula_reduced")
      or ""
    ).strip():
      excluded["missing_formula"] += 1
      continue
    if str(record.get("functional") or "").strip().lower() != "pbe":
      excluded["functional_not_pbe"] += 1
      continue
    if not _compatible(record.get("cross_compatibility", True)):
      excluded["not_cross_compatible"] += 1
      continue
    if int(record.get("nperiodic_dimensions", 3) or 0) != 3:
      excluded["not_three_periodic_dimensions"] += 1
      continue
    if not _structure_valid(record):
      excluded["invalid_structure"] += 1
      continue
    eligible.append(dict(record))
  return eligible, dict(sorted(excluded.items()))


def _deduplicate(
  records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
  by_id: dict[str, dict[str, Any]] = {}
  duplicate_ids = 0
  for record in sorted(records, key=lambda item: canonical_json(item)):
    identifier = str(record["immutable_id"])
    if identifier in by_id:
      duplicate_ids += 1
      continue
    by_id[identifier] = record
  by_fingerprint: dict[str, dict[str, Any]] = {}
  output: list[dict[str, Any]] = []
  fingerprint_collisions = 0
  for identifier, record in sorted(by_id.items()):
    fingerprint = record.get("entalpic_fingerprint")
    if fingerprint is None or str(fingerprint).strip() == "":
      output.append(record)
      continue
    key = canonical_json(fingerprint)
    if key in by_fingerprint:
      fingerprint_collisions += 1
      continue
    by_fingerprint[key] = record
    output.append(record)
  return output, {
    "duplicate_immutable_ids_removed": duplicate_ids,
    "enthalpic_fingerprint_collisions_removed": fingerprint_collisions,
  }


def _allocate_quotas(
  populations: dict[str, int],
  target: int,
) -> tuple[dict[str, int], dict[str, int], list[dict[str, Any]]]:
  keys = sorted(populations)
  population_total = sum(populations.values())
  ideal = {
    key: target * (0.8 * populations[key] / population_total + 0.2 / len(keys))
    for key in keys
  }
  initial = {key: math.floor(ideal[key]) for key in keys}
  remaining = target - sum(initial.values())
  for key in sorted(keys, key=lambda item: (-(ideal[item] - initial[item]), item))[:remaining]:
    initial[key] += 1

  quotas = {key: min(initial[key], populations[key]) for key in keys}
  redistributions: list[dict[str, Any]] = []
  shortfall = target - sum(quotas.values())
  iteration = 0
  while shortfall:
    capacity = {key: populations[key] - quotas[key] for key in keys if populations[key] > quotas[key]}
    if not capacity:
      raise ValueError("quota redistribution exhausted all strata before reaching target")
    iteration += 1
    additions = _largest_remainder_with_capacity(capacity, shortfall)
    moved = sum(additions.values())
    if moved <= 0:
      raise ValueError("quota redistribution made no progress")
    for key, amount in additions.items():
      quotas[key] += amount
    redistributions.append(
      {"iteration": iteration, "shortfall_before": shortfall, "additions": additions}
    )
    shortfall -= moved
  return quotas, initial, redistributions


def _largest_remainder_with_capacity(
  capacity: dict[str, int],
  seats: int,
) -> dict[str, int]:
  total_capacity = sum(capacity.values())
  assignable = min(seats, total_capacity)
  ideal = {key: assignable * value / total_capacity for key, value in capacity.items()}
  additions = {key: min(math.floor(ideal[key]), capacity[key]) for key in capacity}
  remaining = assignable - sum(additions.values())
  order = sorted(
    capacity,
    key=lambda key: (-(ideal[key] - additions[key]), key),
  )
  while remaining:
    progressed = False
    for key in order:
      if additions[key] >= capacity[key]:
        continue
      additions[key] += 1
      remaining -= 1
      progressed = True
      if remaining == 0:
        break
    if not progressed:
      break
  return {key: value for key, value in additions.items() if value}


def _selection_hash(identifier: str) -> str:
  payload = canonical_json([INDEX_SEED, identifier]).encode("utf-8")
  return hashlib.sha256(payload).hexdigest()


def _stratum_key(record: dict[str, Any]) -> str:
  nelements = int(record.get("nelements") or len(record.get("elements") or []))
  nsites = int(record.get("nsites") or len(record.get("species_at_sites") or []))
  magnetization = record.get("total_magnetization") is not None
  forces = record.get("forces") is not None
  return "|".join([
    _source_family(str(record.get("immutable_id") or ""), record),
    _bin(nelements, [(1, "1"), (2, "2"), (3, "3"), (4, "4"), (10**9, "5+")]),
    _bin(nsites, [(4, "1-4"), (8, "5-8"), (16, "9-16"), (32, "17-32"), (64, "33-64"), (10**9, "65+")]),
    f"m{int(magnetization)}f{int(forces)}",
  ])


def _source_family(identifier: str, record: dict[str, Any]) -> str:
  explicit = record.get("source_family") or record.get("source") or record.get("source_dataset")
  if explicit:
    return str(explicit).lower()
  match = re.match(r"[A-Za-z_-]+", identifier)
  return match.group(0).lower().rstrip("_-") if match else "unknown"


def _bin(value: int, bins: list[tuple[int, str]]) -> str:
  return next(label for maximum, label in bins if value <= maximum)


def _compatible(value: object) -> bool:
  if isinstance(value, bool):
    return value
  if isinstance(value, str):
    return value.strip().lower() in {"true", "1", "yes", "compatible", "pbe"}
  if isinstance(value, (list, tuple, set)):
    return any(str(item).lower() == "pbe" for item in value)
  return bool(value)


def _structure_valid(record: dict[str, Any]) -> bool:
  lattice = record.get("lattice_vectors")
  species = record.get("species_at_sites")
  coordinates = record.get("cartesian_site_positions")
  structure = record.get("structure")
  if isinstance(structure, dict):
    lattice = structure.get("lattice", lattice)
    species = structure.get("species", species)
    coordinates = structure.get("coords", coordinates)
  if not isinstance(lattice, (list, tuple)) or len(lattice) != 3:
    return False
  try:
    matrix = np.asarray(lattice, dtype=float)
  except (TypeError, ValueError):
    return False
  if matrix.shape != (3, 3) or not np.isfinite(matrix).all() or abs(np.linalg.det(matrix)) <= 1e-12:
    return False
  return (
    isinstance(species, (list, tuple))
    and isinstance(coordinates, (list, tuple))
    and len(species) > 0
    and len(species) == len(coordinates)
    and all(isinstance(site, (list, tuple)) and len(site) == 3 for site in coordinates)
    and all(
      all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in site)
      for site in coordinates
    )
  )


def _coverage(records: list[dict[str, Any]]) -> dict[str, int]:
  return {
    "total_magnetization_reported": sum(
      record.get("total_magnetization") is not None for record in records
    ),
    "forces_reported": sum(record.get("forces") is not None for record in records),
    "structure_valid": sum(_structure_valid(record) for record in records),
  }
