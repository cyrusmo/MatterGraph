from __future__ import annotations

from typing import Any

from mattergraph.schema.structure import CrystalStructure

from mattergraph_sim.job_spec import AseJobSpec, SimulationJob


def _load_ase() -> tuple[Any, Any, Any]:
  try:
    from ase.calculators.emt import EMT
    from ase.optimize import BFGS
    from pymatgen.io.ase import AseAtomsAdaptor
  except ImportError as e:
    msg = "Install the optional `ase` dependency to run local ASE relaxations."
    raise ImportError(msg) from e
  return EMT, BFGS, AseAtomsAdaptor


def _crystal_to_ase(c: CrystalStructure) -> Any:
  s = c.to_pymatgen()
  _, _, AseAtomsAdaptor = _load_ase()
  return AseAtomsAdaptor.get_atoms(s)  # type: ignore[return-value]


def ase_relax(job: SimulationJob) -> SimulationJob:
  """
  Local relaxation using ASE + EMT (MVP). Swap calculators for your own backend as needed.
  """
  EMT, BFGS, _ = _load_ase()
  spec: AseJobSpec = job.spec
  c = CrystalStructure.model_validate(job.input_structure)
  atoms = _crystal_to_ase(c)
  if spec.calc_name != "emt":
    msg = "MVP only supports EMT; extend mattergraph-sim for other calculators"
    raise ValueError(msg)
  atoms.calc = EMT()
  opt = BFGS(atoms)
  opt.run(fmax=spec.fmax, steps=spec.max_steps)
  f = atoms.get_forces() if atoms.calc is not None else None
  e = atoms.get_potential_energy() if atoms.calc is not None else None
  fmaxf = float((f**2).sum() ** 0.5) if f is not None else None
  return job.model_copy(
    update={
      "status": "completed",
      "log": f"E={e!s} fmax={fmaxf!s}" if fmaxf is not None else f"E={e!s} fmax=n/a",
    }
  )
