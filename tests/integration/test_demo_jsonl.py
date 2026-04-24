from pathlib import Path

from mattergraph import MaterialStore

ROOT = Path(__file__).resolve().parents[2]


def test_demo_loads() -> None:
  p = ROOT / "data" / "demo" / "materials_sample.jsonl"
  s = MaterialStore.from_jsonl(p)
  assert len(s.materials) >= 1
