from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel

from mattergraph.schema.context import PropertyContext, Quantity, SourceArtifact
from mattergraph.schema.dataset import DatasetManifest
from mattergraph.schema.material import Material
from mattergraph.schema.property import MaterialProperty
from mattergraph.schema.provenance import ProvenanceRecord
from mattergraph.schema.result import SimulationResultEnvelope
from mattergraph.schema.simulation import SimulationJobRef
from mattergraph.schema.structure import CrystalStructure


SCHEMA_MODELS: dict[str, type[BaseModel]] = {
  "crystal-structure.schema.json": CrystalStructure,
  "dataset.schema.json": DatasetManifest,
  "material.schema.json": Material,
  "property-context.schema.json": PropertyContext,
  "property.schema.json": MaterialProperty,
  "provenance.schema.json": ProvenanceRecord,
  "quantity.schema.json": Quantity,
  "simulation-result.schema.json": SimulationResultEnvelope,
  "simulation.schema.json": SimulationJobRef,
  "source-artifact.schema.json": SourceArtifact,
}


def generate_schema_documents() -> Iterator[tuple[str, dict[str, Any]]]:
  """Yield canonical JSON Schema documents derived only from Pydantic models."""
  for filename, model in SCHEMA_MODELS.items():
    document = model.model_json_schema(mode="validation")
    document["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    document["$id"] = f"https://mattergraph.dev/schemas/0.1/{filename}"
    yield filename, document


def canonical_schema_json(document: dict[str, Any]) -> str:
  return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
