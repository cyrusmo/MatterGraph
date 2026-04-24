from __future__ import annotations

from fastapi import APIRouter, HTTPException
from mattergraph_sim.ase_runner import ase_relax
from mattergraph_sim.job_spec import AseJobSpec, SimulationJob
from pydantic import BaseModel, Field

from app.services import store_service

router = APIRouter()


class RelaxRequest(BaseModel):
  material_id: str
  spec: AseJobSpec = Field(default_factory=AseJobSpec)


@router.post("/simulations/ase/relax")
def run_relax(body: RelaxRequest) -> dict:
  store = store_service.get_store()
  m = store.get(body.material_id)
  if m is None or m.structure is None:
    raise HTTPException(status_code=400, detail="material or structure missing")
  st = m.structure
  job = SimulationJob(
    spec=body.spec,
    input_structure=st.to_json_dict(),
  )
  out = ase_relax(job)
  return out.model_dump()
