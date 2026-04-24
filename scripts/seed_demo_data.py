#!/usr/bin/env python3
"""Print a short summary of the bundled demo JSONL (no network)."""

from pathlib import Path

from mattergraph import MaterialStore


def main() -> None:
  root = Path(__file__).resolve().parents[1]
  p = root / "data" / "demo" / "materials_sample.jsonl"
  store = MaterialStore.from_jsonl(p)
  print(f"Loaded {len(store.materials)} materials from {p}")
  for m in store.materials:
    print(f"  {m.material_id}  {m.formula}")


if __name__ == "__main__":
  main()
