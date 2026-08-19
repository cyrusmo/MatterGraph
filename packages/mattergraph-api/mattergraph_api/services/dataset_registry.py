from __future__ import annotations

import gc
import threading
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Any

from mattergraph import DatasetManifest, MaterialStore

MAX_DATASETS = 8
MAX_NORMALIZED_BYTES = 32 * 1024 * 1024


class DatasetRegistryError(RuntimeError):
  pass


class DatasetNotFoundError(DatasetRegistryError):
  def __init__(self, dataset_id: str, *, evicted: bool = False) -> None:
    self.dataset_id = dataset_id
    self.evicted = evicted
    label = "evicted" if evicted else "unknown"
    super().__init__(f"{label} dataset {dataset_id!r}")


class DatasetBusyError(DatasetRegistryError):
  pass


class DatasetCapacityError(DatasetRegistryError):
  pass


@dataclass(frozen=True)
class RegistryEntry:
  manifest: DatasetManifest
  payload: bytes


class DatasetRegistry:
  """Byte-budgeted LRU registry with one lazily materialized store."""

  def __init__(
    self,
    *,
    max_entries: int = MAX_DATASETS,
    max_bytes: int = MAX_NORMALIZED_BYTES,
  ) -> None:
    self.max_entries = max_entries
    self.max_bytes = max_bytes
    self._entries: OrderedDict[str, RegistryEntry] = OrderedDict()
    self._lock = threading.RLock()
    self._active_dataset_id: str | None = None
    self._active_store: MaterialStore | None = None
    self._evicted_ids: deque[str] = deque(maxlen=64)

  @property
  def total_bytes(self) -> int:
    with self._lock:
      return sum(len(entry.payload) for entry in self._entries.values())

  @property
  def active_dataset_id(self) -> str | None:
    with self._lock:
      return self._active_dataset_id

  def register(self, manifest: DatasetManifest, payload: bytes) -> dict[str, Any]:
    if len(payload) != manifest.normalized_bytes:
      msg = "manifest normalized_bytes does not match the payload"
      raise ValueError(msg)
    if len(payload) > self.max_bytes:
      msg = f"normalized payload exceeds registry byte budget of {self.max_bytes}"
      raise DatasetCapacityError(msg)
    with self._lock:
      prior = self._entries.pop(manifest.dataset_id, None)
      if prior is not None and self._active_dataset_id == manifest.dataset_id:
        self._release_active_locked()
      self._entries[manifest.dataset_id] = RegistryEntry(manifest=manifest, payload=payload)
      evicted = self._evict_to_budget_locked(protected_id=manifest.dataset_id)
      return {
        "manifest": manifest.model_dump(mode="json"),
        "evicted_dataset_ids": evicted,
        "registry": self.stats(),
      }

  def list(self) -> list[dict[str, Any]]:
    with self._lock:
      return [
        self._entry_status(dataset_id, entry)
        for dataset_id, entry in reversed(self._entries.items())
      ]

  def get(self, dataset_id: str) -> RegistryEntry:
    with self._lock:
      entry = self._entry_locked(dataset_id)
      self._entries.move_to_end(dataset_id)
      return entry

  def status(self, dataset_id: str) -> dict[str, Any]:
    with self._lock:
      entry = self._entry_locked(dataset_id)
      self._entries.move_to_end(dataset_id)
      return self._entry_status(dataset_id, entry)

  def materialize(self, dataset_id: str) -> MaterialStore:
    with self._lock:
      entry = self._entry_locked(dataset_id)
      self._entries.move_to_end(dataset_id)
      if self._active_dataset_id == dataset_id and self._active_store is not None:
        return self._active_store

      # Enforce the single-store invariant before parsing the next payload.
      self._release_active_locked()
      gc.collect()
      try:
        store = MaterialStore.from_jsonl_text(
          entry.payload.decode("utf-8"),
          max_rows=entry.manifest.record_count,
        )
      except Exception:
        self._active_dataset_id = None
        self._active_store = None
        raise
      self._active_dataset_id = dataset_id
      self._active_store = store
      return store

  def export(self, dataset_id: str) -> tuple[DatasetManifest, bytes]:
    entry = self.get(dataset_id)
    return entry.manifest, entry.payload

  def delete(self, dataset_id: str) -> DatasetManifest:
    if not self._lock.acquire(blocking=False):
      msg = f"dataset {dataset_id!r} is currently being replaced or deleted"
      raise DatasetBusyError(msg)
    try:
      entry = self._entry_locked(dataset_id)
      if self._active_dataset_id == dataset_id:
        self._release_active_locked()
      del self._entries[dataset_id]
      return entry.manifest
    finally:
      self._lock.release()

  def clear(self) -> None:
    with self._lock:
      self._release_active_locked()
      self._entries.clear()
      self._evicted_ids.clear()

  def stats(self) -> dict[str, int | str | None]:
    with self._lock:
      return {
        "entry_count": len(self._entries),
        "normalized_bytes": sum(len(entry.payload) for entry in self._entries.values()),
        "max_entries": self.max_entries,
        "max_normalized_bytes": self.max_bytes,
        "active_dataset_id": self._active_dataset_id,
        "eviction_policy": "weighted_lru",
      }

  def _entry_locked(self, dataset_id: str) -> RegistryEntry:
    entry = self._entries.get(dataset_id)
    if entry is None:
      raise DatasetNotFoundError(dataset_id, evicted=dataset_id in self._evicted_ids)
    return entry

  def _entry_status(self, dataset_id: str, entry: RegistryEntry) -> dict[str, Any]:
    return {
      "manifest": entry.manifest.model_dump(mode="json"),
      "readiness": "ready",
      "normalized_bytes": len(entry.payload),
      "materialized": dataset_id == self._active_dataset_id and self._active_store is not None,
      "eviction": {
        "policy": "least_recently_used",
        "entry_limit": self.max_entries,
        "byte_limit": self.max_bytes,
      },
    }

  def _evict_to_budget_locked(self, *, protected_id: str) -> list[str]:
    evicted: list[str] = []
    while len(self._entries) > self.max_entries or self.total_bytes > self.max_bytes:
      victim = next((key for key in self._entries if key != protected_id), None)
      if victim is None:
        msg = "registry limits cannot accommodate the normalized dataset"
        raise DatasetCapacityError(msg)
      if victim == self._active_dataset_id:
        self._release_active_locked()
      del self._entries[victim]
      self._evicted_ids.append(victim)
      evicted.append(victim)
    return evicted

  def _release_active_locked(self) -> None:
    self._active_store = None
    self._active_dataset_id = None


dataset_registry = DatasetRegistry()
