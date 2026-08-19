from __future__ import annotations

from fastapi import APIRouter, HTTPException
from mattergraph_sim.job_spec import AseJobSpec, SimulationJob
from pydantic import BaseModel, Field

from mattergraph_api.services import store_service
from mattergraph_api.services.demo_service import get_chgnet_reference_artifact

router = APIRouter()


@router.get("/simulations/chgnet/reference/{material_id}")
def get_chgnet_reference(material_id: str) -> dict:
  artifact = get_chgnet_reference_artifact()
  if artifact is None:
    raise HTTPException(status_code=503, detail="verified CHGNet reference is unavailable")
  if artifact["material_id"] != material_id:
    raise HTTPException(status_code=404, detail="no CHGNet reference for this material")
  return artifact


class RelaxRequest(BaseModel):
  material_id: str
  dataset_id: str | None = None
  spec: AseJobSpec = Field(default_factory=AseJobSpec)


@router.post("/simulations/ase/relax")
def run_relax(body: RelaxRequest) -> dict:
  try:
    from mattergraph_sim import ase_relax
  except ImportError as e:
    raise HTTPException(status_code=503, detail=str(e)) from e

  store = store_service.resolve_store(body.dataset_id)
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
