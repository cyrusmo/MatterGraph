"""Example: build a simple crystal graph from a demo material."""

from pathlib import Path

from mattergraph import MaterialStore
from mattergraph.graph.crystal_graph import CrystalGraphBuilder

root = Path(__file__).resolve().parents[1]
store = MaterialStore.from_jsonl(root / "data" / "demo" / "materials_sample.jsonl")
m0 = store.materials[0]
if m0.structure is None:
  msg = "demo material has no structure"
  raise SystemExit(msg)
b = CrystalGraphBuilder(cutoff_radius=3.0, max_neighbors=8)
g = b.build(m0.structure)
print("num_atoms", g.num_atoms, "edges", g.edge_index.shape, "global", g.global_features)
