from __future__ import annotations

from fastapi import APIRouter, Query

from mattergraph_api.services import store_service

router = APIRouter()


@router.get("/search")
def search(
  element: str | None = Query(
    default=None, description="Filter materials whose elements contain this symbol, e.g. Fe"
  ),
  dataset_id: str | None = Query(default=None),
) -> list[dict]:
  store = store_service.resolve_store(dataset_id)
  out = []
  for m in store.materials:
    if not element:
      out.append(m.model_dump())
      continue
    e = element.strip()
    if e in m.elements:
      out.append(m.model_dump())
  return out
