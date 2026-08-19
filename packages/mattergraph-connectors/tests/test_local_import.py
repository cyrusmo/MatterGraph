import json
from pathlib import Path

import pytest
from mattergraph.schema.generation import canonical_schema_json
from mattergraph_connectors.local_import import (
  DatasetImportMapping,
  ImportLimitError,
  ImportValidationError,
  PropertyColumnMapping,
  import_local_content,
  inspect_local_content,
)
from mattergraph_connectors.schema_generation import generate_import_schema_documents


def test_inspect_and_import_csv_is_deterministic() -> None:
  content = "material_id,formula,density\na,AlN,3.26\nb,TiN,5.22\n"
  inspection = inspect_local_content(filename="sample.csv", format="csv", content=content)
  assert inspection.status == "ready"
  assert inspection.row_count == 2
  assert inspection.inferred_mapping is not None

  first = import_local_content(filename="sample.csv", format="csv", content=content)
  second = import_local_content(filename="renamed.csv", format="csv", content=content)
  # Provenance intentionally records only the safe basename, so a rename changes normalized data.
  assert first.result.dataset_id != second.result.dataset_id
  repeated = import_local_content(filename="sample.csv", format="csv", content=content)
  assert repeated.result.dataset_id == first.result.dataset_id
  assert first.result.manifest.normalized_bytes == len(first.normalized_jsonl)


def test_strict_rejection_and_degraded_skip() -> None:
  content = "material_id,formula,density\na,AlN,3.26\nb,not-an-element,4.0\n"
  with pytest.raises(ImportValidationError) as error:
    import_local_content(filename="mixed.csv", format="csv", content=content)
  assert error.value.report.status == "invalid"

  imported = import_local_content(
    filename="mixed.csv",
    format="csv",
    content=content,
    error_policy="skip_invalid_rows",
  )
  assert imported.result.manifest.degraded
  assert imported.result.accepted_count == 1
  assert imported.result.rejected_count == 1


def test_duplicate_id_invalid_structure_unknown_unit_and_mixed_methods() -> None:
  structure = json.dumps(
    {"lattice": [[3, 0, 0], [0, 3, 0], [0, 0, 3]], "species": ["Al"], "coords": []}
  )
  escaped_structure = structure.replace('"', '""')
  content = (
    "material_id,formula,structure_json,density,energy\n"
    f'a,AlN,"{escaped_structure}",3.2,-1\n'
    "b,AlN,,3.3,-2\n"
    "b,AlN,,3.4,-3\n"
  )
  mapping = DatasetImportMapping(
    structure_column="structure_json",
    property_columns=[
      PropertyColumnMapping(column="density", name="density", unit="mystery", method="dft"),
      PropertyColumnMapping(column="energy", name="energy", unit="eV", method="experimental"),
    ],
  )
  with pytest.raises(ImportValidationError) as error:
    import_local_content(filename="bad.csv", format="csv", content=content, mapping=mapping)
  codes = error.value.report.issue_counts
  assert codes["unknown_unit"] == 1
  assert codes["mixed_methods"] == 1
  assert codes["invalid_structure"] == 1
  assert codes["duplicate_id"] == 1


def test_jsonl_roundtrip_and_bounds() -> None:
  content = '{"material_id":"a","formula":"AlN","properties":[]}\n'
  imported = import_local_content(filename="records.jsonl", format="jsonl", content=content)
  assert imported.result.preview[0]["material_id"] == "a"
  assert b'"material_id": "a"' in imported.normalized_jsonl

  with pytest.raises(ImportLimitError):
    inspect_local_content(filename="too-big.csv", format="csv", content="x" * (5 * 1024 * 1024 + 1))


def test_checked_in_import_schemas_match_pydantic_models() -> None:
  schema_dir = Path("data/schemas")
  for filename, document in generate_import_schema_documents():
    assert (schema_dir / filename).read_text() == canonical_schema_json(document)
