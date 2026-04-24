from pathlib import Path

import pytest
from mattergraph import Material, MaterialProperty, MaterialStore
from mattergraph.graph.crystal_graph import CrystalGraphBuilder
from mattergraph.schema.structure import CrystalStructure


def test_material_composition() -> None:
  m = Material(
    material_id="1",
    formula="Fe2O3",
  )
  assert m.reduced_formula in ("Fe2O3", "Fe2O3")  # exact reduced
  assert "Fe" in m.elements
  assert "O" in m.elements


def test_crystal_from_pymatgen_roundtrip() -> None:
  from pymatgen.core import Lattice, Structure

  s = Structure(Lattice.cubic(3.0), ["Na", "Cl"], [[0, 0, 0], [0.5, 0, 0]])
  c = CrystalStructure.from_pymatgen(s)
  s2 = c.to_pymatgen()
  assert len(s2) == 2
  b = CrystalGraphBuilder(cutoff_radius=3.0, max_neighbors=8)
  g = b.build(c)
  assert g.num_atoms == 2
  assert g.node_features.shape[0] == 2
  assert g.edge_index.size > 0 or g.num_atoms <= 1


def test_from_demo() -> None:
  store = MaterialStore.from_demo()
  if not store.materials:
    sample = Path("data/demo/materials_sample.jsonl")
    if not sample.is_file():
      pytest.skip("no demo data")
  assert len(store.materials) > 0


def test_property_numeric() -> None:
  m = Material(
    material_id="a",
    formula="Fe",
    properties=[MaterialProperty(name="density", value=7.8, source="mp", method="dft")],
  )
  assert m.get_numeric("density") == 7.8
