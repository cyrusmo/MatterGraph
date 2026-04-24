#!/usr/bin/env python3
"""Load a small slice of JARVIS-DFT 3D (first run may download data)."""

from mattergraph_connectors import JarvisConnector


def main() -> None:
  c = JarvisConnector()
  mats = c.fetch(elements=["Ti"], max_records=5)
  print(f"Loaded {len(mats)} materials")
  for m in mats:
    print(m.material_id, m.formula)


if __name__ == "__main__":
  main()
