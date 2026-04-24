from __future__ import annotations

import contextlib
import io
from typing import Any

import numpy as np
from mattergraph.schema.structure import CrystalStructure

from mattergraph_sim.job_spec import AseJobSpec, SimulationJob, SimulationResult

EMT_SUPPORTED_SPECIES = (
  "Ag",
  "Al",
  "Au",
  "C",
  "Cu",
  "H",
  "N",
  "Ni",
  "O",
  "Pd",
  "Pt",
)


def _load_ase() -> tuple[Any, Any, Any]:
  try:
    from ase.calculators.emt import EMT
    from ase.optimize import BFGS
    from pymatgen.io.ase import AseAtomsAdaptor
  except ImportError as e:
    msg = "Install the optional `ase` dependency to run local ASE relaxations."
    raise ImportError(msg) from e
  return EMT, BFGS, AseAtomsAdaptor


def _failure(job: SimulationJob, error: str) -> SimulationJob:
  return job.model_copy(
    update={
      "status": "failed",
      "error": error,
      "log": error,
      "result": None,
    }
  )


def _supported_species_for(calc_name: str) -> tuple[str, ...]:
  if calc_name == "emt":
    return EMT_SUPPORTED_SPECIES
  return ()


def _unsupported_species(structure: Any, calc_name: str) -> list[str]:
  supported = set(_supported_species_for(calc_name))
  symbols = set(structure.composition.element_composition.as_dict())
  return sorted(symbols - supported)


def ase_relax(job: SimulationJob) -> SimulationJob:
  """
  Local relaxation using ASE + EMT (MVP). Swap calculators for your own backend as needed.
  """
  EMT, BFGS, _ = _load_ase()
  running = job.model_copy(update={"status": "running", "error": None})

  try:
    spec: AseJobSpec = running.spec
    if running.kind != "relax":
      return _failure(running, f"ASE runner only supports kind='relax'; got {running.kind!r}")

    structure = CrystalStructure.model_validate(running.input_structure).to_pymatgen()
    unsupported = _unsupported_species(structure, spec.calc_name)
    if unsupported:
      supported = ", ".join(_supported_species_for(spec.calc_name))
      bad = ", ".join(unsupported)
      return _failure(
        running,
        f"ASE {spec.calc_name} does not support species: {bad}. Supported species: {supported}.",
      )

    _, _, AseAtomsAdaptor = _load_ase()
    atoms = AseAtomsAdaptor.get_atoms(structure)  # type: ignore[assignment]
    atoms.calc = EMT()

    optimizer_log = io.StringIO()
    with contextlib.redirect_stdout(optimizer_log), contextlib.redirect_stderr(optimizer_log):
      opt = BFGS(atoms, logfile=optimizer_log)
      converged = bool(opt.run(fmax=spec.fmax, steps=spec.max_steps))

    forces = atoms.get_forces() if atoms.calc is not None else None
    energy = float(atoms.get_potential_energy()) if atoms.calc is not None else None
    max_force = None
    if forces is not None and len(forces) > 0:
      max_force = float(np.linalg.norm(forces, axis=1).max())

    relaxed_structure = CrystalStructure.from_pymatgen(AseAtomsAdaptor.get_structure(atoms))
    steps = int(getattr(opt, "nsteps", 0))
    summary = (
      f"calculator={spec.calc_name} energy={energy!s} max_force={max_force!s} "
      f"steps={steps} converged={converged}"
    )
    raw_log = optimizer_log.getvalue().strip()
    log = summary if not raw_log else f"{summary}\n{raw_log}"

    return running.model_copy(
      update={
        "status": "completed",
        "log": log,
        "result": SimulationResult(
          engine=spec.engine,
          calculator=spec.calc_name,
          converged=converged,
          steps=steps,
          energy=energy,
          max_force=max_force,
          relaxed_structure=relaxed_structure,
        ),
      }
    )
  except ImportError:
    raise
  except Exception as e:  # noqa: BLE001
    return _failure(running, f"{type(e).__name__}: {e}")
