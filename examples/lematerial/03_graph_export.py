from __future__ import annotations

import json
from pathlib import Path

from mattergraph_connectors import LeMatBulk

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "data" / "demo" / "lemat_bulk_sample.json"


def main() -> None:
  records = json.loads(FIXTURE_PATH.read_text())
  dataset = LeMatBulk.from_records(records, subset="compatible_pbesol")
  result = dataset.to_graphs()
  print(
    json.dumps(
      {
        "included_count": result.included_count,
        "excluded_count": result.excluded_count,
        "material_ids": [row["material_id"] for row in result.graphs],
      },
      indent=2,
      sort_keys=True,
    )
  )


if __name__ == "__main__":
  main()
