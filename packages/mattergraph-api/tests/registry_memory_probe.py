"""Child process workload for the registry RSS budget test."""

from __future__ import annotations

import json
import sys

from mattergraph_api.services.dataset_registry import DatasetRegistry
from mattergraph_connectors.local_import import import_local_content


def main() -> int:
  # The exact 8-entry/32-MiB limits are covered separately. A seven-entry
  # process probe makes the eighth sequential import exercise count-based LRU
  # eviction while leaving headroom for the one active 5,000-row store.
  registry = DatasetRegistry(max_entries=7)
  print("READY", flush=True)
  if sys.stdin.readline().strip() != "go":
    return 2

  note = "x" * 180
  ids: list[str] = []
  for dataset_index in range(8):
    rows = ["material_id,formula,density,notes"]
    rows.extend(
      f"m{dataset_index}-{row},AlN,{3.2 + dataset_index / 100:.2f},{note}"
      for row in range(5_000)
    )
    imported = import_local_content(
      filename=f"stress-{dataset_index}.csv",
      format="csv",
      content="\n".join(rows) + "\n",
    )
    registry.register(imported.result.manifest, imported.normalized_jsonl)
    ids.append(imported.result.dataset_id)

  retained_ids = [entry["manifest"]["dataset_id"] for entry in registry.list()]
  for _pass in range(2):
    for dataset_id in retained_ids:
      store = registry.materialize(dataset_id)
      if len(store.materials) != 5_000:
        return 3

  print(
    json.dumps(
      {
        "import_count": len(ids),
        "retained_count": len(retained_ids),
        "evicted_count": len(ids) - len(retained_ids),
        "stats": registry.stats(),
      }
    ),
    flush=True,
  )
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
