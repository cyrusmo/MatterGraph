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

  # Read the audit before the ranking: it names any objective that was ignored for having
  # no coverage or no spread, and how many candidates the hard constraints removed.
  report = sc.report(store.materials)
  print(json.dumps(report, indent=2))
  print()

  df = sc.rank(store.materials)
  print(df.to_string(index=False))

  out = df.copy().round(4)
  out.insert(0, "rank", range(1, len(out) + 1))
  out.to_csv(ROOT / "shortlist_example.csv", index=False)
  (ROOT / "shortlist_report.json").write_text(json.dumps(report, indent=2) + "\n")
  print("\nWrote shortlist_example.csv and shortlist_report.json")


if __name__ == "__main__":
  main()
