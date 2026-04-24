from typing import Literal

from mattergraph.schema.structure import CrystalStructure
from mattergraph_sim.ase_runner import ase_relax
from mattergraph_sim.job_spec import AseJobSpec, SimulationJob


def _job_for(
  structure: CrystalStructure,
  *,
  kind: Literal["relax", "sc", "md"] = "relax",
) -> SimulationJob:
  return SimulationJob(
    spec=AseJobSpec(),
    input_structure=structure.to_json_dict(),
    kind=kind,
  )


def test_ase_relax_returns_structured_result_for_supported_species() -> None:
  structure = CrystalStructure(
    lattice=[[4.04, 0.0, 0.0], [0.0, 4.04, 0.0], [0.0, 0.0, 4.04]],
    species=["Al"],
    coords=[[0.0, 0.0, 0.0]],
  )

  out = ase_relax(_job_for(structure))

  assert out.status == "completed"
  assert out.error is None
  assert out.result is not None
  assert out.result.calculator == "emt"
  assert out.result.energy is not None
  assert out.result.max_force is not None
  assert out.result.relaxed_structure is not None
  assert "calculator=emt" in (out.log or "")


def test_ase_relax_fails_gracefully_for_unsupported_species() -> None:
  structure = CrystalStructure(
    lattice=[[2.8, 0.0, 0.0], [0.0, 2.8, 0.0], [0.0, 0.0, 2.8]],
    species=["Fe"],
    coords=[[0.0, 0.0, 0.0]],
  )

  out = ase_relax(_job_for(structure))

  assert out.status == "failed"
  assert out.result is None
  assert out.error is not None
  assert "does not support species: Fe" in out.error


def test_ase_relax_rejects_non_relax_jobs() -> None:
  structure = CrystalStructure(
    lattice=[[4.04, 0.0, 0.0], [0.0, 4.04, 0.0], [0.0, 0.0, 4.04]],
    species=["Al"],
    coords=[[0.0, 0.0, 0.0]],
  )

  out = ase_relax(_job_for(structure, kind="md"))

  assert out.status == "failed"
  assert out.error == "ASE runner only supports kind='relax'; got 'md'"
