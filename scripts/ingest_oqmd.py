#!/usr/bin/env python3
"""OQMD has no native connector in this repo — reach it through OPTIMADE instead.

This script used to print "OQMD stub returned 0 materials." and exit 0, which reads as a
successful query that matched nothing. The connector now raises, and this reports that.
"""

from mattergraph_connectors import OQMDStubConnector


def main() -> None:
  c = OQMDStubConnector()
  try:
    materials = c.fetch()
  except NotImplementedError as exc:
    print(f"OQMD connector unavailable: {exc}")
    raise SystemExit(1) from exc
  print("OQMD returned", len(materials), "materials.")


if __name__ == "__main__":
  main()
