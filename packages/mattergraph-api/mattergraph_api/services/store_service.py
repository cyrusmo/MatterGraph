from __future__ import annotations

import os
from pathlib import Path

from mattergraph import MaterialStore

from mattergraph_api.services.demo_service import get_demo_store

_store: MaterialStore | None = None


def _resolve_demo_path() -> Path | None:
  env = os.environ.get("MATTERGRAPH_DEMO_DATA")
  if env:
    return Path(env)
  return None


def get_store() -> MaterialStore:
  global _store  # noqa: PLW0603
  if _store is None:
    p = _resolve_demo_path()
    _store = MaterialStore.from_jsonl(p) if p is not None and p.is_file() else get_demo_store()
  return _store


def reset_store(s: MaterialStore) -> None:
  global _store  # noqa: PLW0603
  _store = s
