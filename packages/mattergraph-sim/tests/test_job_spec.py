from mattergraph_sim.job_spec import AseJobSpec, SimulationJob
from mattergraph_sim.lammps_runner import run_lammps


def test_simulation_job_defaults() -> None:
  job = SimulationJob(spec=AseJobSpec(), input_structure={})
  assert job.kind == "relax"
  assert job.status == "pending"
  failed = run_lammps(job)
  assert failed.status == "failed"
