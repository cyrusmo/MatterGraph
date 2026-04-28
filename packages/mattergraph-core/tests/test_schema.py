from pathlib import Path

import pytest
from mattergraph import Material, MaterialProperty, MaterialStore
from mattergraph.schema.provenance import ProvenanceRecord
from mattergraph.schema.simulation import SimulationJobRef
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


def test_material_rejects_inconsistent_reduced_formula_and_elements() -> None:
  with pytest.raises(ValueError, match="reduced_formula must match formula"):
    Material(material_id="1", formula="Fe2O3", reduced_formula="FeO")
  with pytest.raises(ValueError, match="elements must match formula"):
    Material(material_id="1", formula="Fe2O3", elements=["Fe"])


def test_property_and_provenance_validation() -> None:
  prop = MaterialProperty(name=" density ", value="7.8", source=" mp ", method="dft")
  assert prop.name == "density"
  assert prop.source == "mp"

  prov = ProvenanceRecord(source=" jarvis ", method="experimental", confidence=0.5)
  assert prov.source == "jarvis"
  assert prov.method == "experimental"

  with pytest.raises(ValueError, match="confidence must be between 0 and 1"):
    MaterialProperty(name="density", value=7.8, source="mp", confidence=1.1)
  with pytest.raises(ValueError, match="uncertainty must be non-negative"):
    MaterialProperty(name="density", value=7.8, source="mp", uncertainty=-0.1)
  with pytest.raises(ValueError, match="confidence must be between 0 and 1"):
    ProvenanceRecord(source="mp", confidence=-0.1)


def test_crystal_structure_rejects_bad_shapes_and_singular_lattice() -> None:
  with pytest.raises(ValueError, match="each coordinate must have length 3"):
    CrystalStructure(
      lattice=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
      species=["Fe"],
      coords=[[0.0, 0.0]],
    )
  with pytest.raises(ValueError, match="lattice volume must be positive"):
    CrystalStructure(
      lattice=[[1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
      species=["Fe"],
      coords=[[0.0, 0.0, 0.0]],
    )


def test_simulation_job_ref_validation() -> None:
  ref = SimulationJobRef(job_id=" sim-1 ", engine="ase", status="completed")
  assert ref.job_id == "sim-1"

  with pytest.raises(ValueError, match="job_id must not be empty"):
    SimulationJobRef(job_id="   ")
