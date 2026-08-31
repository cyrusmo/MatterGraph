from pathlib import Path

import numpy as np
import pytest
from mattergraph import (
  Material,
  MaterialProperty,
  MaterialStore,
  PropertyContext,
  Quantity,
  SourceArtifact,
)
from pymatgen.core import Lattice, Structure
from mattergraph.schema.provenance import ProvenanceRecord
from mattergraph.schema.simulation import SimulationJobRef
from mattergraph.graph.crystal_graph import CrystalGraphBuilder
from mattergraph.normalization.structures import check_density
from mattergraph.schema.structure import CrystalStructure
from mattergraph.schema.generation import canonical_schema_json, generate_schema_documents


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


@pytest.mark.parametrize(
  ("structure", "expected_first_shell"),
  [
    (
      lambda: Structure.from_spacegroup(
        "Fm-3m",
        Lattice.cubic(4.24),
        ["Ti", "N"],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
      ),
      6,
    ),
    (
      lambda: Structure(
        Lattice.hexagonal(3.11, 4.98),
        ["Al", "Al", "N", "N"],
        [[1 / 3, 2 / 3, 0], [2 / 3, 1 / 3, 0.5], [1 / 3, 2 / 3, 0.382], [2 / 3, 1 / 3, 0.882]],
      ),
      4,
    ),
  ],
)
def test_crystal_graph_first_shell_coordination_and_reciprocity(
  structure: object,
  expected_first_shell: int,
) -> None:
  s = structure()
  graph = CrystalGraphBuilder(cutoff_radius=5.0, max_neighbors=12).build(
    CrystalStructure.from_pymatgen(s)
  )
  edges = [
    (
      int(graph.edge_index[0, index]),
      int(graph.edge_index[1, index]),
      tuple(int(value) for value in graph.image_offsets[index]),
      float(graph.edge_features[index, 0]),
    )
    for index in range(graph.edge_index.shape[1])
  ]
  edge_keys = {(source, target, image) for source, target, image, _distance in edges}
  assert all((target, source, tuple(-value for value in image)) in edge_keys for source, target, image, _distance in edges)
  assert all(distance > 0 for _source, _target, _image, distance in edges)
  for atom in range(graph.num_atoms):
    distances = [distance for source, _target, _image, distance in edges if source == atom]
    first = min(distances)
    assert sum(distance <= first + 0.1 for distance in distances) == expected_first_shell


def test_crystal_graph_displacement_reconstructs_periodic_endpoint() -> None:
  from pymatgen.core import Lattice, Structure

  structure = Structure(Lattice.cubic(3.0), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
  graph = CrystalGraphBuilder(cutoff_radius=4.0, max_neighbors=8).build(
    CrystalStructure.from_pymatgen(structure)
  )
  for index in range(graph.edge_index.shape[1]):
    source = graph.edge_index[0, index]
    target = graph.edge_index[1, index]
    image = graph.image_offsets[index]
    expected = structure.lattice.get_cartesian_coords(
      graph.fractional_coordinates[target] + image - graph.fractional_coordinates[source]
    )
    assert graph.displacement_vectors[index] == pytest.approx(expected)
    assert graph.edge_features[index, 0] == pytest.approx(float(np.linalg.norm(expected)))


def test_crystal_graph_rejects_disorder_explicitly() -> None:
  from pymatgen.core import Lattice, Structure

  disordered = Structure(Lattice.cubic(3.0), [{"Fe": 0.5, "Mn": 0.5}], [[0, 0, 0]])
  with pytest.raises(ValueError, match="disordered"):
    CrystalGraphBuilder().build(CrystalStructure.from_pymatgen(disordered))


def test_crystal_graph_is_invariant_to_integer_periodic_wrapping() -> None:
  structure = Structure(Lattice.cubic(4.2), ["Ti", "N"], [[0, 0, 0], [0.5, 0.5, 0.5]])
  shifted = Structure(Lattice.cubic(4.2), ["Ti", "N"], [[1, -1, 0], [0.5, 1.5, -0.5]])
  builder = CrystalGraphBuilder(cutoff_radius=5.0, max_neighbors=12)
  original_graph = builder.build(CrystalStructure.from_pymatgen(structure))
  shifted_graph = builder.build(CrystalStructure.from_pymatgen(shifted))
  assert original_graph.edge_index.tolist() == shifted_graph.edge_index.tolist()
  assert original_graph.edge_features[:, 0].tolist() == pytest.approx(
    shifted_graph.edge_features[:, 0].tolist()
  )


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


def test_from_demo_is_available_outside_repository(
  monkeypatch: pytest.MonkeyPatch,
  tmp_path: Path,
) -> None:
  monkeypatch.chdir(tmp_path)
  store = MaterialStore.from_demo()
  assert len(store.materials) == 3
  assert [material.material_id for material in store.materials] == [
    "demo-fe-bcc-1",
    "demo-ti-bcc-1",
    "demo-al-fcc-1",
  ]


def test_check_density_diagnoses_incomplete_basis() -> None:
  # bcc iron written with only the corner atom: the cell holds half its basis, so the
  # real density is ~2x what the cell implies. This is the defect the guardrail exists
  # for, and the ratio should name it.
  incomplete = CrystalStructure(
    lattice=[[2.8665, 0.0, 0.0], [0.0, 2.8665, 0.0], [0.0, 0.0, 2.8665]],
    species=["Fe"],
    coords=[[0.0, 0.0, 0.0]],
  )
  bad = check_density(incomplete, 7.874)
  assert not bad.consistent
  assert bad.ratio == pytest.approx(2.0, abs=0.05)
  assert bad.diagnosis is not None
  assert "1/2" in bad.diagnosis

  complete = incomplete.model_copy(
    update={"species": ["Fe", "Fe"], "coords": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]]}
  )
  good = check_density(complete, 7.874)
  assert good.consistent
  assert good.computed == pytest.approx(7.874, rel=1e-3)


def test_demo_structures_match_stated_density() -> None:
  """Every demo record's structure must agree with the density it reports.

  Guards the whole `data/demo` fixture set: removing a basis atom from any record makes
  this fail, which is how the previous simple-cubic placeholders shipped unnoticed.
  """
  store = MaterialStore.from_demo()
  if not store.materials:
    pytest.skip("no demo data")

  checked = 0
  for material in store.materials:
    stated = material.get_numeric("density")
    if material.structure is None or stated is None:
      continue
    result = check_density(material.structure, stated)
    assert result.consistent, f"{material.material_id}: {result.diagnosis}"
    checked += 1
  assert checked > 0, "no demo record carried both a structure and a density"


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
        context=PropertyContext(
          temperature=Quantity(value=298.15, unit="K"),
          environment="ambient air",
          test_method="computed reference",
        ),
        source_artifact=SourceArtifact(
          citation="Example source",
          revision="2024.01",
          license="CC-BY-4.0",
          checksum_sha256="a" * 64,
        ),
        extra={"raw_field": "energy_above_hull"},
      )
    ],
    provenance=[
      ProvenanceRecord(
        source="materials_project",
        source_id="task-1",
        model_version="2024.01",
        parameters={"functional": "PBE"},
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
  assert loaded.materials[0].properties[0].context is not None
  assert loaded.materials[0].properties[0].context.temperature is not None
  assert loaded.materials[0].properties[0].context.temperature.value == pytest.approx(298.15)
  assert loaded.materials[0].properties[0].source_artifact is not None
  assert loaded.materials[0].properties[0].source_artifact.license == "CC-BY-4.0"
  assert loaded.materials[0].provenance[0].model_version == "2024.01"
  assert loaded.materials[0].provenance[0].parameters == {"functional": "PBE"}


def test_in_memory_jsonl_roundtrip_preserves_legacy_shape() -> None:
  legacy = '{"material_id":"legacy-1","formula":"AlN","properties":[]}\n'
  store = MaterialStore.from_jsonl_text(legacy)
  assert store.materials[0].material_id == "legacy-1"
  reloaded = MaterialStore.from_jsonl_text(store.to_jsonl_text())
  assert reloaded.materials[0].formula == "AlN"


def test_checked_in_json_schemas_match_pydantic_models() -> None:
  schema_dir = Path("data/schemas")
  for filename, document in generate_schema_documents():
    assert (schema_dir / filename).read_text() == canonical_schema_json(document)


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
