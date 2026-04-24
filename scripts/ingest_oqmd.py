#!/usr/bin/env python3
"""OQMD connector is a stub in the public repo — wire your query client here."""

from mattergraph_connectors import OQMDStubConnector


def main() -> None:
  c = OQMDStubConnector()
  print("OQMD stub returned", len(c.fetch()), "materials.")


if __name__ == "__main__":
  main()
