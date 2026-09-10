from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from mattergraph.navigator.models import ConstraintPlan
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mattergraph_api.services import navigator_service

router = APIRouter(prefix="/navigator")


class InterpretRequest(BaseModel):
  model_config = ConfigDict(extra="forbid")

  text: str = Field(max_length=2_000)

  @field_validator("text")
  @classmethod
  def _nonempty(cls, value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
      raise ValueError("text must not be empty")
    return cleaned


class ReplayCreateRequest(BaseModel):
  model_config = ConfigDict(extra="forbid")

  plan: ConstraintPlan
  public_opt_in: bool = False


@router.get("/registry")
def registry() -> dict[str, Any]:
  runtime = navigator_service.get_runtime()
  return {
    **runtime.registry.model_dump(mode="json"),
    "record_count": len(runtime.records),
    "source_kind": runtime.source_kind,
    "scope": "compatible_pbe three-dimensional bulk structures",
  }


@router.get("/model-contract")
def model_contract() -> dict[str, Any]:
  return navigator_service.model_contract()


@router.post("/interpret")
def interpret(request: InterpretRequest) -> dict[str, Any]:
  runtime = navigator_service.get_runtime()
  return runtime.interpreter.interpret(request.text).model_dump(mode="json")


@router.post("/validate")
def validate(plan: ConstraintPlan) -> dict[str, Any]:
  return navigator_service.get_runtime().engine.validate(plan).model_dump(mode="json")


@router.post("/evaluate")
def evaluate(plan: ConstraintPlan) -> dict[str, Any]:
  return navigator_service.get_runtime().engine.evaluate(plan).model_dump(mode="json")


@router.post("/relaxations")
def relaxations(plan: ConstraintPlan) -> dict[str, Any]:
  return navigator_service.get_runtime().engine.relaxations(plan).model_dump(mode="json")


@router.get("/materials/{material_id}")
def material(material_id: str) -> dict[str, Any]:
  payload = navigator_service.material_payload(material_id)
  if payload is None:
    raise HTTPException(status_code=404, detail="navigator material not found")
  if payload["structure"] is None:
    raise HTTPException(status_code=422, detail="source-backed structure contract is unavailable")
  return payload


@router.post("/replays")
def create_replay(request: ReplayCreateRequest) -> dict[str, Any]:
  try:
    return navigator_service.create_public_replay(
      request.plan,
      public_opt_in=request.public_opt_in,
    )
  except ValueError as exc:
    raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/replays/{replay_id}")
def replay(replay_id: str) -> dict[str, Any]:
  payload = navigator_service.get_public_replay(replay_id)
  if payload is None:
    raise HTTPException(status_code=404, detail="replay not found")
  return payload
