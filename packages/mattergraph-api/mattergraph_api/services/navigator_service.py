from __future__ import annotations

import hashlib
import json
import os
import secrets
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mattergraph.navigator import (
  ConstraintPlan,
  DeterministicInterpreter,
  NavigatorEngine,
  NavigatorRecord,
  PropertyRegistry,
  default_registry,
  freeze_numeric_bounds,
  navigator_record_from_material,
)
from mattergraph_connectors import LeMatBulk

from mattergraph_api.services import store_service

MODEL_CONTRACT_RELATIVE_PATH = "configs/navigator/model_contract.json"
MAX_PUBLIC_REPLAYS = 64


@dataclass(frozen=True)
class NavigatorRuntime:
  records: list[NavigatorRecord]
  registry: PropertyRegistry
  engine: NavigatorEngine
  interpreter: DeterministicInterpreter
  source_kind: str


_runtime_store_identity: int | None = None
_runtime_index_path: str | None = None
_runtime: NavigatorRuntime | None = None
_public_replays: OrderedDict[str, dict[str, Any]] = OrderedDict()


def get_runtime() -> NavigatorRuntime:
  global _runtime, _runtime_index_path, _runtime_store_identity  # noqa: PLW0603
  configured_index = os.environ.get("MATTERGRAPH_NAVIGATOR_INDEX_RAW")
  if configured_index:
    records = _configured_index_records(configured_index)
    identity = id(records)
  else:
    store = store_service.get_store()
    records = [navigator_record_from_material(material) for material in store.materials]
    identity = id(store)
  if (
    _runtime is not None
    and _runtime_store_identity == identity
    and _runtime_index_path == configured_index
  ):
    return _runtime
  if configured_index and len(records) != 25_000:
    raise ValueError(
      f"configured navigator index must contain exactly 25000 records; found {len(records)}"
    )
  index_id = "index_v1" if configured_index else "demo_snapshot_v1"
  registry = freeze_numeric_bounds(default_registry(index_id=index_id), records)
  _runtime = NavigatorRuntime(
    records=records,
    registry=registry,
    engine=NavigatorEngine(records, registry),
    interpreter=DeterministicInterpreter(registry),
    source_kind="frozen_index" if index_id == "index_v1" else "checksummed_real_snapshot",
  )
  _runtime_store_identity = identity
  _runtime_index_path = configured_index
  return _runtime


def model_contract() -> dict[str, Any]:
  path = _repo_root() / MODEL_CONTRACT_RELATIVE_PATH
  return json.loads(path.read_text())


def material_payload(material_id: str) -> dict[str, Any] | None:
  runtime = get_runtime()
  record = next((item for item in runtime.records if item.material_id == material_id), None)
  if record is None:
    return None
  return {
    "material_id": record.material_id,
    "formula": record.formula,
    "elements": record.elements,
    "nsites": record.nsites,
    "functional": record.functional,
    "properties": record.properties,
    "property_provenance": record.property_provenance,
    "structure": record.structure.model_dump(mode="json") if record.structure else None,
    "inspection_boundary": (
      "Rendering supports inspection of source-backed geometry; it is not structural validation."
    ),
  }


def create_public_replay(plan: ConstraintPlan, *, public_opt_in: bool) -> dict[str, Any]:
  if not public_opt_in:
    raise ValueError("public_opt_in must be true; private replay remains client-local")
  runtime = get_runtime()
  evaluation = runtime.engine.evaluate(plan)
  canonical = {
    "plan": plan.model_dump(mode="json"),
    "registry_digest": runtime.registry.digest,
    "index_id": runtime.registry.index_id,
    "engine_version": runtime.engine.version,
  }
  plan_hash = hashlib.sha256(
    json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
  ).hexdigest()
  replay_id = secrets.token_urlsafe(24)
  payload = {
    "replay_id": replay_id,
    "plan_hash": plan_hash,
    "confirmed_plan": plan.model_dump(mode="json"),
    "result": evaluation.model_dump(mode="json"),
    "privacy": (
      "Explicitly public replay: confirmed plan and deterministic result only; no raw prompt "
      "or provider output is retained."
    ),
  }
  _public_replays[replay_id] = payload
  _public_replays.move_to_end(replay_id)
  while len(_public_replays) > MAX_PUBLIC_REPLAYS:
    _public_replays.popitem(last=False)
  return payload


def get_public_replay(replay_id: str) -> dict[str, Any] | None:
  payload = _public_replays.get(replay_id)
  if payload is not None:
    _public_replays.move_to_end(replay_id)
  return payload


def _repo_root() -> Path:
  configured = os.environ.get("MATTERGRAPH_REPO_ROOT")
  if configured:
    return Path(configured).resolve()
  return Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class _IndexCache:
  path: str
  modified_ns: int
  records: list[NavigatorRecord]


_index_cache: _IndexCache | None = None


def _configured_index_records(path_value: str) -> list[NavigatorRecord]:
  global _index_cache  # noqa: PLW0603
  path = Path(path_value).resolve()
  if not path.is_file():
    raise ValueError(f"configured navigator index does not exist: {path}")
  modified_ns = path.stat().st_mtime_ns
  if _index_cache and _index_cache.path == str(path) and _index_cache.modified_ns == modified_ns:
    return _index_cache.records
  raw_records = [
    json.loads(line)
    for line in path.read_text(encoding="utf-8").splitlines()
    if line.strip()
  ]
  store = LeMatBulk.from_records(
    raw_records,
    source_dataset="LeMaterial/LeMat-Bulk",
    subset="compatible_pbe",
  ).to_material_store()
  raw_by_id = {str(record["immutable_id"]): record for record in raw_records}
  records = [
    navigator_record_from_material(
      material,
      raw_record=raw_by_id.get(
        str(material.metadata.get("immutable_id") or material.material_id)
      ),
    )
    for material in store.materials
  ]
  _index_cache = _IndexCache(path=str(path), modified_ns=modified_ns, records=records)
  return records
