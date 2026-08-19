from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from mattergraph import Material

from mattergraph_api.services import store_service
from mattergraph_api.services.demo_service import graph_summary

router = APIRouter()


@router.get("/materials")
def list_materials(dataset_id: str | None = Query(default=None)) -> list[dict]:
  store = store_service.resolve_store(dataset_id)
  return [m.model_dump() for m in store.materials]


@router.get("/materials/{mid}")
def get_material(mid: str, dataset_id: str | None = Query(default=None)) -> dict:
  store = store_service.resolve_store(dataset_id)
  m: Material | None = store.get(mid)
  if m is None:
    raise HTTPException(status_code=404, detail="not found")
  return m.model_dump()


@router.get("/materials/{mid}/graph-summary")
def get_material_graph_summary(
  mid: str, dataset_id: str | None = Query(default=None)
) -> dict:
  store = store_service.resolve_store(dataset_id)
  material: Material | None = store.get(mid)
  if material is None:
    raise HTTPException(status_code=404, detail="not found")
  try:
    return graph_summary(material)
  except ValueError as exc:
    raise HTTPException(status_code=422, detail=str(exc)) from exc
