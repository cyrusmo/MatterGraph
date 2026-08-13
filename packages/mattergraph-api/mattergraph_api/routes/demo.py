from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from mattergraph_api.services import store_service
from mattergraph_api.services.demo_service import (
  DEFAULT_CONSTRAINTS,
  DEFAULT_OBJECTIVES,
  FIXTURE_DISCLAIMER,
  FIXTURE_RELATIVE_PATH,
  capability_catalog,
  chgnet_state,
  get_default_material_id,
  get_default_scorecard,
  get_demo_manifest,
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
  graph_invalid = 0
  for material in store.materials:
    try:
      summary = graph_summary(material, max_edges=0)
      graph_ready += 1
      if summary["validation"]["state"] != "valid":
        graph_invalid += 1
    except ValueError:
      graph_excluded += 1

  scorecard = get_default_scorecard()
  score_report = scorecard.report(store.materials)
  simulation_targets = {
    material.material_id: simulation_readiness(material) for material in store.materials
  }
  default_material_id = get_default_material_id()
  manifest = get_demo_manifest()
  ml_state = chgnet_state()
  checks = [
    {
      "id": "fixture",
      "status": "pass" if store.materials else "fail",
      "detail": f"{len(store.materials)} normalized records",
    },
    {
      "id": "graphs",
      "status": "pass" if graph_ready and not graph_invalid else "fail",
      "detail": (
        f"{graph_ready} graph-ready; {graph_excluded} excluded; {graph_invalid} invalid"
      ),
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
      "id": "ml_reference",
      "status": "pass" if ml_state["reference_available"] else "warn",
      "detail": str(ml_state["detail"]),
    },
  ]
  overall = "ready" if all(check["status"] == "pass" for check in checks) else "degraded"
  return {
    "status": overall,
    "fixture": {
      "path": FIXTURE_RELATIVE_PATH,
      "kind": "checksummed_real_snapshot",
      "disclaimer": FIXTURE_DISCLAIMER,
      "dataset": manifest["dataset"],
      "subset": manifest["subset"],
      "upstream_revision": manifest["upstream_revision"],
      "hull_dataset": manifest["hull_dataset"],
      "hull_revision": manifest["hull_revision"],
      "license": manifest["license"],
      "citation_doi": manifest["citation_doi"],
      "snapshot_sha256": manifest["snapshot_sha256"],
      "source_population": manifest["source_population"],
      "field_sources": manifest["field_sources"],
    },
    "record_count": len(store.materials),
    "graph": {
      "included_count": graph_ready,
      "excluded_count": graph_excluded,
      "invalid_count": graph_invalid,
      "validation_state": "valid" if graph_ready and not graph_invalid else "invalid",
    },
    "ranking": {
      "ranked_count": score_report["ranked_count"],
      "excluded_by_constraints": score_report["excluded_by_constraints"],
      "binary_normalization": score_report["binary_normalization"],
      "objectives": DEFAULT_OBJECTIVES,
      "constraints": DEFAULT_CONSTRAINTS,
    },
    "default_material_id": default_material_id,
    "chgnet": ml_state,
    "simulation_targets": simulation_targets,
    "checks": checks,
  }
