from __future__ import annotations

import os
from pathlib import Path

from mattergraph import MaterialStore

_store: MaterialStore | None = None


def _resolve_demo_path() -> Path:
  env = os.environ.get("MATTERGRAPH_DEMO_DATA")
  if env:
    return Path(env)
  for p in (
    Path("data/demo/materials_sample.jsonl"),
    Path(__file__).resolve().parents[4] / "data" / "demo" / "materials_sample.jsonl",
  ):
    if p.is_file():
      return p
  return Path("data/demo/materials_sample.jsonl")


def get_store() -> MaterialStore:
  global _store  # noqa: PLW0603
  if _store is None:
    p = _resolve_demo_path()
    _store = MaterialStore.from_jsonl(p) if p.is_file() else MaterialStore()
  return _store


def reset_store(s: MaterialStore) -> None:
  global _store  # noqa: PLW0603
  _store = s
