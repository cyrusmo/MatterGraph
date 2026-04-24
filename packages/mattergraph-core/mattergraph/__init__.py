"""MatterGraph core: materials schema, crystal graphs, and basic scoring."""

from importlib import metadata

from mattergraph.schema.material import Material
from mattergraph.schema.property import MaterialProperty
from mattergraph.schema.provenance import ProvenanceRecord
from mattergraph.scoring.scorecard import Scorecard
from mattergraph.store import MaterialStore

__all__ = [
  "Material",
  "MaterialProperty",
  "ProvenanceRecord",
  "MaterialStore",
  "Scorecard",
  "__version__",
]

try:
  __version__ = metadata.version("mattergraph-core")
except metadata.PackageNotFoundError:
  __version__ = "0.0.0"
