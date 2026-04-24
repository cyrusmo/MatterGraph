from __future__ import annotations

import json
from pathlib import Path

import yaml
from mattergraph import MaterialStore, Scorecard

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main() -> None:
  cfg = yaml.safe_load((ROOT / "constraints.yaml").read_text())
  obj_raw: dict = cfg.get("objectives", {})
  con = dict(cfg.get("constraints", {}))
  obj_dirs: dict[str, str] = {}
  weights: dict[str, float] = {}
  for k, v in obj_raw.items():
    if not isinstance(v, dict):
      continue
    obj_dirs[k] = v.get("direction", "maximize")
    weights[k] = float(v.get("weight", 1.0))
  store = MaterialStore.from_jsonl(REPO / "data" / "demo" / "materials_sample.jsonl")
  sc = Scorecard(objectives=obj_dirs, constraints=con, weights=weights)
  df = sc.rank(store.materials)
  print(df.to_string(index=False))
  (ROOT / "shortlist_out.json").write_text(json.dumps(df.to_dict(orient="records"), indent=2))
  print("Wrote shortlist_out.json")


if __name__ == "__main__":
  main()
