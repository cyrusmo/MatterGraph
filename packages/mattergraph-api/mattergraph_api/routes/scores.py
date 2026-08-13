from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from mattergraph import Scorecard
from pydantic import BaseModel, ConfigDict, Field

from mattergraph_api.services import store_service

router = APIRouter()


Direction = Literal["minimize", "maximize"]
MissingPolicy = Literal["worst", "neutral", "exclude"]


class ObjectiveConfig(BaseModel):
  model_config = ConfigDict(extra="forbid")

  direction: Direction = "maximize"
  weight: float = Field(default=1.0, ge=0.0)


class ConstraintConfig(BaseModel):
  model_config = ConfigDict(extra="forbid")

  min: float | None = None
  max: float | None = None
  equals: bool | float | str | None = None


class ScoreRequest(BaseModel):
  model_config = ConfigDict(extra="forbid")

  objectives: dict[str, Direction | ObjectiveConfig] = Field(
    default_factory=dict,
  )
  constraints: dict[str, ConstraintConfig] = Field(default_factory=dict)
  weights: dict[str, float] | None = None
  missing: MissingPolicy = "worst"


@router.post("/scores/rank")
def rank(request: ScoreRequest) -> list[dict]:
  store = store_service.get_store()
  sc = _scorecard(request)
  df = sc.rank(store.materials)
  return df.to_dict(orient="records")


@router.post("/scores/rank/audit")
def rank_with_audit(request: ScoreRequest) -> dict[str, Any]:
  store = store_service.get_store()
  scorecard = _scorecard(request)
  ranked = scorecard.rank(store.materials).to_dict(orient="records")
  materials_by_id = {material.material_id: material for material in store.materials}
  for row in ranked:
    material = materials_by_id.get(str(row.get("material_id")))
    if material is None:
      continue
    for property_name in request.constraints:
      row.setdefault(property_name, material.get_numeric(property_name))
  return {
    "ranked": ranked,
    "report": scorecard.report(store.materials),
    "request": request.model_dump(mode="json"),
  }


def _scorecard(request: ScoreRequest) -> Scorecard:
  payload = request.model_dump(mode="python", exclude_none=True)
  return Scorecard(
    objectives=payload["objectives"],
    constraints=payload["constraints"],
    weights=payload.get("weights"),
    missing=payload["missing"],
  )
