#!/usr/bin/env python3
"""Fetch a few Materials Project entries (requires MP_API_KEY)."""

import os
import sys

from mattergraph_connectors import MaterialsProjectConnector


def main() -> None:
  if not os.environ.get("MP_API_KEY") and not os.environ.get("MATERIALS_PROJECT_API_KEY"):
    print("Set MP_API_KEY to a valid Materials Project API key.", file=sys.stderr)
    sys.exit(1)
  mp = MaterialsProjectConnector()
  mats = mp.fetch(elements=["Fe", "Ti"], chunk_size=5, num_chunks=1)
  print(f"Fetched {len(mats)} materials")
  for m in mats[:5]:
    print(m.material_id, m.formula)


if __name__ == "__main__":
  main()
