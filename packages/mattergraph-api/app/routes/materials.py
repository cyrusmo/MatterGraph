from __future__ import annotations

from fastapi import APIRouter, HTTPException
from mattergraph import Material

from app.services import store_service

router = APIRouter()


@router.get("/materials")
def list_materials() -> list[dict]:
  store = store_service.get_store()
  return [m.model_dump() for m in store.materials]


@router.get("/materials/{mid}")
def get_material(mid: str) -> dict:
  store = store_service.get_store()
  m: Material | None = store.get(mid)
  if m is None:
    raise HTTPException(status_code=404, detail="not found")
  return m.model_dump()
