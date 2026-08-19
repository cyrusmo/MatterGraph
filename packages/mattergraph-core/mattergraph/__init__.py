"""MatterGraph core: materials schema, crystal graphs, and basic scoring."""

from importlib import metadata

from mattergraph.schema.context import PropertyContext, Quantity, SourceArtifact
from mattergraph.schema.dataset import DatasetManifest
from mattergraph.schema.material import Material
from mattergraph.schema.property import MaterialProperty
from mattergraph.schema.provenance import ProvenanceRecord
from mattergraph.schema.result import SimulationResultEnvelope
from mattergraph.scoring.scorecard import Scorecard
from mattergraph.store import MaterialStore

__all__ = [
  "DatasetManifest",
  "Material",
  "MaterialProperty",
  "PropertyContext",
  "ProvenanceRecord",
  "Quantity",
  "SimulationResultEnvelope",
  "SourceArtifact",
  "MaterialStore",
  "Scorecard",
  "__version__",
]

try:
  __version__ = metadata.version("mattergraph-core")
except metadata.PackageNotFoundError:
  __version__ = "0.0.0"
