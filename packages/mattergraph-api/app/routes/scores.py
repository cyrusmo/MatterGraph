from __future__ import annotations

from fastapi import APIRouter
from mattergraph import Scorecard
from pydantic import BaseModel, Field

from app.services import store_service

router = APIRouter()


class ScoreRequest(BaseModel):
  objectives: dict[str, str] = Field(
    default_factory=dict,
  )
  constraints: dict[str, dict] = Field(default_factory=dict)
  weights: dict[str, float] | None = None


@router.post("/scores/rank")
def rank(request: ScoreRequest) -> list[dict]:
  store = store_service.get_store()
  sc = Scorecard(
    objectives=request.objectives,  # type: ignore[arg-type]
    constraints=request.constraints,  # type: ignore[arg-type]
    weights=request.weights,
  )
  df = sc.rank(store.materials)
  return df.to_dict(orient="records")
