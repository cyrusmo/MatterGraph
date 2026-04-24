"""Example: ASE EMT relaxation on a demo structure (``mattergraph-sim``)."""

from pathlib import Path

from mattergraph import MaterialStore
from mattergraph_sim.ase_runner import ase_relax
from mattergraph_sim.job_spec import AseJobSpec, SimulationJob

root = Path(__file__).resolve().parents[1]
store = MaterialStore.from_jsonl(root / "data" / "demo" / "materials_sample.jsonl")
material = next((m for m in store.materials if m.material_id == "demo-al-fcc-1"), None)
if material is None or material.structure is None:
  raise SystemExit("demo-al-fcc-1 structure not found")
st = material.structure
job = SimulationJob(spec=AseJobSpec(), input_structure=st.to_json_dict(), kind="relax")
out = ase_relax(job)
print(out.model_dump())
