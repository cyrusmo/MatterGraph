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
  assert g.edge_features.shape[1] == 4
  assert g.image_offsets.shape[0] == g.edge_features.shape[0]


def test_crystal_graph_is_deterministic() -> None:
  from pymatgen.core import Lattice, Structure

  s = Structure(Lattice.cubic(3.0), ["Na", "Cl"], [[0, 0, 0], [0.5, 0, 0]])
  c = CrystalStructure.from_pymatgen(s)
  b = CrystalGraphBuilder(cutoff_radius=4.0, max_neighbors=8)
  g1 = b.build(c)
  g2 = b.build(c)
  assert g1.edge_index.tolist() == g2.edge_index.tolist()
  assert g1.image_offsets.tolist() == g2.image_offsets.tolist()
  assert g1.edge_features.tolist() == g2.edge_features.tolist()


def test_crystal_roundtrip_preserves_site_properties_and_disorder() -> None:
  from pymatgen.core import Lattice, Species, Structure

  ordered = Structure(
    Lattice.cubic(3.0),
    [Species("Fe", 2)],
    [[0, 0, 0]],
    site_properties={"magmom": [2.2]},
  )
  c = CrystalStructure.from_pymatgen(ordered)
  assert c.site_properties == [{"magmom": 2.2}]
  assert c.to_pymatgen()[0].properties["magmom"] == 2.2

  disordered = Structure(
    Lattice.cubic(3.0),
    [{"Fe": 0.5, "Mn": 0.5}],
    [[0, 0, 0]],
  )
  d = CrystalStructure.from_pymatgen(disordered)
  assert isinstance(d.species[0], dict)
  assert d.to_pymatgen()[0].species.num_atoms == pytest.approx(1.0)


def test_from_demo() -> None:
  store = MaterialStore.from_demo()
  if not store.materials:
    sample = Path("data/demo/materials_sample.jsonl")
    if not sample.is_file():
      pytest.skip("no demo data")
  assert len(store.materials) > 0


def test_store_jsonl_roundtrip(tmp_path: Path) -> None:
  m = Material(
    material_id="mp-1",
    formula="Fe2O3",
    source_id="mp-1",
    properties=[
      MaterialProperty(
        name="e_hull",
        value=0.01,
        unit="eV/atom",
        source="materials_project",
        source_id="task-1",
        extra={"raw_field": "energy_above_hull"},
      )
    ],
    provenance=[
      ProvenanceRecord(
        source="materials_project",
        source_id="task-1",
        model_version="2024.01",
      )
    ],
  )
  store = MaterialStore([m])
  path = tmp_path / "materials.jsonl"
  store.to_jsonl(path)
  loaded = MaterialStore.from_jsonl(path)
  assert loaded.materials[0].material_id == "mp-1"
  assert loaded.materials[0].source_id == "mp-1"
  assert loaded.materials[0].properties[0].name == "energy_above_hull"
  assert loaded.materials[0].properties[0].source_id == "task-1"
  assert loaded.materials[0].properties[0].extra["raw_field"] == "energy_above_hull"
  assert loaded.materials[0].provenance[0].model_version == "2024.01"


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
