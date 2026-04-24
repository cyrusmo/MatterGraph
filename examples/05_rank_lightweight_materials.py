"""Example: toy multi-objective ranking on demo data."""

from pathlib import Path

from mattergraph import MaterialStore, Scorecard

root = Path(__file__).resolve().parents[1]
store = MaterialStore.from_jsonl(root / "data" / "demo" / "materials_sample.jsonl")
sc = Scorecard(
  objectives={"density": "minimize", "bulk_modulus": "maximize"},
  constraints={"energy_above_hull": {"max": 0.05}},
)
print(sc.rank(store.materials))
