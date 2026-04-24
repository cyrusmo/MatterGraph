from __future__ import annotations

from mattergraph_sim.job_spec import SimulationJob


def run_lammps(_job: SimulationJob) -> SimulationJob:
  """Stub: LAMMPS integration is environment-specific. Implement where binaries exist."""
  return _job.model_copy(update={"status": "failed", "log": "LAMMPS runner not installed (stub)."})
