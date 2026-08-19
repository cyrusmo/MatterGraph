#!/usr/bin/env python3
"""Regenerate checked-in JSON Schemas from mattergraph-core Pydantic models."""

from __future__ import annotations

import argparse
from pathlib import Path

from mattergraph.schema.generation import canonical_schema_json, generate_schema_documents
from mattergraph_connectors.schema_generation import generate_import_schema_documents


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--check", action="store_true", help="Fail when checked-in schemas drift")
  args = parser.parse_args()

  destination = Path(__file__).resolve().parents[1] / "data" / "schemas"
  mismatches: list[str] = []
  documents = [*generate_schema_documents(), *generate_import_schema_documents()]
  for filename, document in documents:
    path = destination / filename
    expected = canonical_schema_json(document)
    if args.check:
      if not path.is_file() or path.read_text() != expected:
        mismatches.append(filename)
    else:
      path.write_text(expected)

  if mismatches:
    print("Schema drift detected: " + ", ".join(mismatches))
    print("Run: python scripts/generate_schemas.py")
    return 1
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
