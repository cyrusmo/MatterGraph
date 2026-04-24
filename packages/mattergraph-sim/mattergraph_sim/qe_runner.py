from __future__ import annotations

from mattergraph_sim.job_spec import SimulationJob


def run_quantum_espresso(_job: SimulationJob) -> SimulationJob:
  """Stub: QE paths and pseudos are site-specific. Wire up in your environment."""
  return _job.model_copy(
    update={
      "status": "failed",
      "error": "QE runner not installed (stub).",
      "log": "QE runner not installed (stub).",
      "result": None,
    }
  )
