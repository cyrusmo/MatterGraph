from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from mattergraph_api.services import store_service
from mattergraph_api.services.demo_service import (
  DEFAULT_CONSTRAINTS,
  DEFAULT_MATERIAL_ID,
  DEFAULT_OBJECTIVES,
  FIXTURE_DISCLAIMER,
  FIXTURE_RELATIVE_PATH,
  capability_catalog,
  get_default_scorecard,
  graph_summary,
  simulation_readiness,
)

router = APIRouter()


@router.get("/capabilities")
def capabilities() -> dict[str, list[dict[str, Any]]]:
  return {"capabilities": capability_catalog()}


@router.get("/demo/preflight")
def demo_preflight() -> dict[str, Any]:
  store = store_service.get_store()
  graph_ready = 0
  graph_excluded = 0
  for material in store.materials:
    try:
      graph_summary(material, max_edges=0)
      graph_ready += 1
    except ValueError:
      graph_excluded += 1

  scorecard = get_default_scorecard()
  score_report = scorecard.report(store.materials)
  simulation_targets = {
    material.material_id: simulation_readiness(material) for material in store.materials
  }
  default_readiness = simulation_targets.get(DEFAULT_MATERIAL_ID, {"ready": False})
  checks = [
    {
      "id": "fixture",
      "status": "pass" if store.materials else "fail",
      "detail": f"{len(store.materials)} normalized records",
    },
    {
      "id": "graphs",
      "status": "pass" if graph_ready else "fail",
      "detail": f"{graph_ready} graph-ready; {graph_excluded} explicitly excluded",
    },
    {
      "id": "ranking",
      "status": "pass" if score_report["ranked_count"] >= 3 else "warn",
      "detail": (
        f"{score_report['ranked_count']} rank-eligible; "
        f"{score_report['excluded_by_constraints']} excluded"
      ),
    },
    {
      "id": "simulation",
      "status": "pass" if default_readiness.get("ready") else "warn",
      "detail": str(default_readiness.get("reason", "Default target unavailable.")),
    },
  ]
  overall = "ready" if all(check["status"] == "pass" for check in checks) else "degraded"
  return {
    "status": overall,
    "fixture": {
      "path": FIXTURE_RELATIVE_PATH,
      "kind": "illustrative_schema_fixture",
      "disclaimer": FIXTURE_DISCLAIMER,
    },
    "record_count": len(store.materials),
    "graph": {"included_count": graph_ready, "excluded_count": graph_excluded},
    "ranking": {
      "ranked_count": score_report["ranked_count"],
      "excluded_by_constraints": score_report["excluded_by_constraints"],
      "binary_normalization": score_report["binary_normalization"],
      "objectives": DEFAULT_OBJECTIVES,
      "constraints": DEFAULT_CONSTRAINTS,
    },
    "default_material_id": DEFAULT_MATERIAL_ID,
    "simulation_targets": simulation_targets,
    "checks": checks,
  }
