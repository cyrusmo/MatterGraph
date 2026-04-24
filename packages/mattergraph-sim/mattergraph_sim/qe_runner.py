from __future__ import annotations

from mattergraph_sim.job_spec import SimulationJob


def run_quantum_espresso(_job: SimulationJob) -> SimulationJob:
  """Stub: QE paths/pseudos are site-specific. Wire up in a private or HPC image."""
  return _job.model_copy(update={"status": "failed", "log": "QE runner not installed (stub)."})
