from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from mattergraph.schema.generation import canonical_schema_json

from mattergraph_connectors.local_import import (
  DatasetImportMapping,
  ImportIssue,
  ImportReport,
  ImportResult,
  PropertyColumnMapping,
)

IMPORT_SCHEMA_MODELS = {
  "dataset-import-mapping.schema.json": DatasetImportMapping,
  "import-issue.schema.json": ImportIssue,
  "import-report.schema.json": ImportReport,
  "import-result.schema.json": ImportResult,
  "property-column-mapping.schema.json": PropertyColumnMapping,
}


def generate_import_schema_documents() -> Iterator[tuple[str, dict[str, Any]]]:
  for filename, model in IMPORT_SCHEMA_MODELS.items():
    document = model.model_json_schema(mode="validation")
    document["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    document["$id"] = f"https://mattergraph.dev/schemas/0.1/{filename}"
    yield filename, document


__all__ = ["canonical_schema_json", "generate_import_schema_documents"]
