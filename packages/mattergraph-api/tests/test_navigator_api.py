from __future__ import annotations

import json
from importlib import resources

import pytest
from httpx import ASGITransport, AsyncClient
from mattergraph_api.main import app

pytestmark = pytest.mark.asyncio


async def test_registry_is_truthful_about_bundled_snapshot() -> None:
  async with _client() as client:
    response = await client.get("/navigator/registry")

  assert response.status_code == 200
  data = response.json()
  assert data["index_id"] == "demo_snapshot_v1"
  assert data["record_count"] == 24
  assert data["source_kind"] == "checksummed_real_snapshot"
  entries = {entry["field"]: entry for entry in data["entries"]}
  assert entries["signed_total_magnetization"]["display_only"] is True
  assert entries["absolute_total_magnetization_per_site"]["confirmation_required"] is True
  assert entries["maximum_force_norm"]["kind"] == "calculation_quality"
  assert entries["energy_above_hull"]["executable"] is False


async def test_interpret_confirm_evaluate_golden_loop() -> None:
  async with _client() as client:
    interpretation = await client.post(
      "/navigator/interpret",
      json={"text": "Find a ternary nitride with fewer than 20 sites and density below 6 g/cm3."},
    )
    assert interpretation.status_code == 200
    body = interpretation.json()
    assert body["interpreter"]["kind"] == "deterministic_fallback"
    plan = body["plan"]
    for constraint in plan["constraints"]:
      constraint["confirmed"] = True
    evaluated = await client.post("/navigator/evaluate", json=plan)

  assert evaluated.status_code == 200
  result = evaluated.json()
  assert result["state"] == "feasible_set"
  assert result["feasible_count"] > 0
  assert any(candidate["status"] == "pass" for candidate in result["candidates"])


async def test_outcome_states_and_recovery_boundaries() -> None:
  async with _client() as client:
    registry = (await client.get("/navigator/registry")).json()
    conflict = _plan(registry, [
      _constraint("a", "elements", "include_all", ["Co"], "categorical"),
      _constraint("b", "elements", "exclude_any", ["Co"], "categorical"),
    ])
    capability = _plan(registry, [
      _constraint("a", "functional", "eq", "scan", "categorical", locked=True),
    ])
    evidence = _plan(registry, [
      _constraint(
        "a",
        "absolute_total_magnetization",
        "lt",
        0.1,
        "physical",
        unit="μB/cell",
      ),
    ])
    empty = _plan(registry, [
      _constraint("a", "density", "lt", 0.01, "physical", unit="g/cm^3"),
    ])

    conflict_result = await client.post("/navigator/evaluate", json=conflict)
    capability_result = await client.post("/navigator/evaluate", json=capability)
    evidence_result = await client.post("/navigator/evaluate", json=evidence)
    empty_result = await client.post("/navigator/evaluate", json=empty)
    recovery = await client.post("/navigator/relaxations", json=empty)

  assert conflict_result.json()["state"] == "plan_conflict"
  assert capability_result.json()["state"] == "index_capability_mismatch"
  assert evidence_result.json()["state"] == "evidence_unknown"
  assert empty_result.json()["state"] == "no_feasible_set"
  recovered = recovery.json()
  assert recovered["physical_relaxations"]
  assert recovered["quality_relaxations"] == []
  assert all(path["causal"] is False for path in recovered["physical_relaxations"])


async def test_material_contract_and_public_replay_exclude_raw_prompt() -> None:
  async with _client() as client:
    registry = (await client.get("/navigator/registry")).json()
    plan = _plan(registry, [
      _constraint("a", "density", "lt", 6.0, "physical", unit="g/cm^3"),
    ])
    evaluation = (await client.post("/navigator/evaluate", json=plan)).json()
    material_id = next(
      candidate["material_id"]
      for candidate in evaluation["candidates"]
      if candidate["status"] == "pass"
    )
    material = await client.get(f"/navigator/materials/{material_id}")
    rejected = await client.post(
      "/navigator/replays",
      json={"plan": plan, "public_opt_in": False},
    )
    created = await client.post(
      "/navigator/replays",
      json={"plan": plan, "public_opt_in": True},
    )
    replay = await client.get(f"/navigator/replays/{created.json()['replay_id']}")

  assert material.status_code == 200
  structure = material.json()["structure"]
  assert structure["lattice_unit"] == "angstrom"
  assert structure["coordinate_convention"] == "fractional"
  assert structure["periodic_axes"] == [True, True, True]
  assert structure["source"] == "LeMaterial/LeMat-Bulk"
  assert rejected.status_code == 422
  assert created.status_code == 200
  serialized = json.dumps(replay.json()).lower()
  assert "raw_prompt" not in serialized
  assert "provider_output" not in serialized
  assert len(replay.json()["plan_hash"]) == 64


async def test_model_contract_omits_sampling_controls_from_generate_contract() -> None:
  assert resources.files("mattergraph.navigator").joinpath("model_contract.json").is_file()
  async with _client() as client:
    response = await client.get("/navigator/model-contract")
  data = response.json()
  generation = data["qwen_candidate"]["generation"]
  assert generation["do_sample"] is False
  assert generation["temperature"] == "unset"
  assert generation["top_p"] == "unset"
  assert generation["top_k"] == "unset"
  assert data["qwen_candidate"]["status"] == "optional_not_qualified"


def _plan(registry: dict, constraints: list[dict]) -> dict:
  return {
    "constraints": constraints,
    "unresolved_constraints": [],
    "registry_version": registry["version"],
    "index_id": registry["index_id"],
    "engine_version": "navigator-engine-v1",
    "interpreter_version": "test",
  }


def _constraint(
  identifier: str,
  field: str,
  operator: str,
  value: object,
  kind: str,
  *,
  unit: str | None = None,
  locked: bool = False,
) -> dict:
  return {
    "id": identifier,
    "field": field,
    "operator": operator,
    "value": value,
    "unit": unit,
    "kind": kind,
    "locked": locked,
    "confirmed": True,
    "label": field,
    "source_text": None,
  }


def _client() -> AsyncClient:
  return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
