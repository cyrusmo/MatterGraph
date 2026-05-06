from __future__ import annotations

import json
from pathlib import Path

from mattergraph_connectors import LeMatBulk

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "data" / "demo" / "lemat_bulk_sample.json"


def main() -> None:
  records = json.loads(FIXTURE_PATH.read_text())
  dataset = LeMatBulk.from_records(records, subset="compatible_pbesol")
  candidate_slice = (
    dataset
    .filter_elements(include=["Ti", "Al", "N"])
    .filter_complexity(max_nsites=4, max_nelements=3)
    .create_slice("marine_pressure_candidates_v0", target="bulk_modulus")
  )
  print(json.dumps(candidate_slice.report(), indent=2, sort_keys=True))


if __name__ == "__main__":
  main()
