import pytest
from mattergraph_sim.job_spec import AseJobSpec, SimulationJob
from mattergraph_sim.lammps_runner import run_lammps


def test_simulation_job_defaults() -> None:
  job = SimulationJob(spec=AseJobSpec(), input_structure={})
  assert job.kind == "relax"
  assert job.status == "pending"
  assert job.result is None
  assert job.error is None
  failed = run_lammps(job)
  assert failed.status == "failed"
  assert failed.error == "LAMMPS runner not installed (stub)."


def test_job_spec_rejects_invalid_values() -> None:
  with pytest.raises(ValueError, match="unsupported ASE calculator"):
    AseJobSpec(calc_name="lj")
  with pytest.raises(ValueError, match="fmax must be positive"):
    AseJobSpec(fmax=0.0)
  with pytest.raises(ValueError, match="max_steps must be at least 1"):
    AseJobSpec(max_steps=0)
