"""Example: ASE EMT relaxation on a demo structure (``mattergraph-sim``)."""

from pathlib import Path

from mattergraph import MaterialStore
from mattergraph_sim.ase_runner import ase_relax
from mattergraph_sim.job_spec import AseJobSpec, SimulationJob

root = Path(__file__).resolve().parents[1]
store = MaterialStore.from_jsonl(root / "data" / "demo" / "materials_sample.jsonl")
m0 = store.materials[0]
if m0.structure is None:
  raise SystemExit("no structure")
st = m0.structure
job = SimulationJob(spec=AseJobSpec(), input_structure=st.to_json_dict(), kind="relax")
out = ase_relax(job)
print(out)
