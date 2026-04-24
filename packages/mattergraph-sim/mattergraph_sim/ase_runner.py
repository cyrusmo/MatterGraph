from __future__ import annotations

from ase import Atoms
from ase.calculators.emt import EMT
from ase.optimize import BFGS
from mattergraph.schema.structure import CrystalStructure

from mattergraph_sim.job_spec import AseJobSpec, SimulationJob


def _crystal_to_ase(c: CrystalStructure) -> Atoms:
  s = c.to_pymatgen()
  from pymatgen.io.ase import AseAtomsAdaptor

  return AseAtomsAdaptor.get_atoms(s)  # type: ignore[return-value]


def ase_relax(job: SimulationJob) -> SimulationJob:
  """
  Local relaxation using ASE + EMT (MVP). Swap calculators for DFT/MLIPs in private workflows.
  """
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
