import json

import pytest
from httpx import ASGITransport, AsyncClient
from mattergraph_api.main import app

pytestmark = pytest.mark.asyncio


async def test_health() -> None:
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test") as ac:
    r = await ac.get("/health")
  assert r.status_code == 200
  assert r.json() == {"status": "ok"}


async def test_materials_list() -> None:
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test") as ac:
    r = await ac.get("/materials")
  assert r.status_code == 200
  data = r.json()
  assert isinstance(data, list)
  assert len(data) >= 1


async def test_lematerial_demo_workflow_contract() -> None:
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test") as ac:
    r = await ac.get("/workflows/lematerial/demo")
  assert r.status_code == 200
  data = r.json()

  assert data["workflow_id"] == "lematerial_bulk_demo"
  assert data["source_dataset"] == "LeMaterial/LeMat-Bulk"
  assert data["source_subset"] == "compatible_pbesol"
  assert data["schema_report"]["row_count"] == 4

  candidate_slice = data["candidate_slice"]
  assert candidate_slice["slice_id"].startswith("mg_slice_")
  assert candidate_slice["slice_name"] == "bulk_modulus_candidates_v0"
  assert candidate_slice["target"] == "bulk_modulus"
  assert candidate_slice["input_count"] == 4
  assert candidate_slice["output_count"] == 4
  assert candidate_slice["removed_count"] == 0
  assert [step["name"] for step in candidate_slice["filter_steps"]] == [
    "filter_elements",
    "filter_complexity",
  ]

  assert data["graph_export"]["included_count"] == 3
  assert data["graph_export"]["excluded_count"] == 1
  assert len(data["graph_export"]["previews"]) == 3
  assert data["candidate_slice"]["report"]["deduplication_basis"] == "structure_fingerprint"
  assert data["benchmark"]["target"] == "bulk_modulus"
  assert data["benchmark"]["row_count"] == 4
  assert 1 <= len(data["benchmark_preview"]) <= 3
  assert {"material_id", "formula", "target"} <= set(data["benchmark_preview"][0])
  assert data["provenance"] == {
    "fixture_path": "data/demo/lemat_bulk_sample.json",
    "loader": "LeMatBulk.from_records",
    "workflow_version": "v0.2",
    "run_id": "lematerial_bulk_demo_static_v0_2",
    "fixture_kind": "illustrative_schema_fixture",
    "disclaimer": (
      "Illustrative bundled records shaped like LeMaterial bulk data. "
      "They demonstrate workflow behavior, not dataset scale or production predictions."
    ),
  }

  serialized = json.dumps(data)
  assert "graphs" not in data
  assert "node_features" not in serialized
  assert "edge_index" not in serialized


async def test_simulation_relax_succeeds_for_supported_demo_material() -> None:
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test") as ac:
    r = await ac.post(
      "/simulations/ase/relax",
      json={"material_id": "lemat-aln"},
    )
  assert r.status_code == 200
  data = r.json()
  assert data["status"] == "completed"
  assert data["error"] is None
  assert data["result"]["calculator"] == "emt"
  assert data["result"]["relaxed_structure"] is not None


async def test_simulation_relax_fails_gracefully_for_unsupported_demo_material() -> None:
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test") as ac:
    r = await ac.post(
      "/simulations/ase/relax",
      json={"material_id": "lemat-tin-alpha"},
    )
  assert r.status_code == 200
  data = r.json()
  assert data["status"] == "failed"
  assert data["result"] is None
  assert "does not support species: Ti" in data["error"]


async def test_demo_preflight_is_ready_and_coherent() -> None:
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test") as ac:
    response = await ac.get("/demo/preflight")

  assert response.status_code == 200
  data = response.json()
  assert data["status"] == "ready"
  assert data["record_count"] == 4
  assert data["graph"] == {"included_count": 3, "excluded_count": 1}
  assert data["ranking"]["ranked_count"] == 3
  assert data["ranking"]["excluded_by_constraints"] == 1
  assert data["ranking"]["binary_normalization"] is False
  assert data["default_material_id"] == "lemat-aln"
  assert data["simulation_targets"]["lemat-aln"]["ready"] is True
  assert data["simulation_targets"]["lemat-tin-alpha"]["ready"] is False


async def test_capability_ledger_distinguishes_ready_stub_and_boundary() -> None:
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test") as ac:
    response = await ac.get("/capabilities")

  assert response.status_code == 200
  capabilities = {item["id"]: item for item in response.json()["capabilities"]}
  assert capabilities["crystal_graphs"]["status"] == "demo_ready"
  assert capabilities["materials_project"]["status"] == "sdk_ready"
  assert capabilities["lammps"]["status"] == "stub"
  assert capabilities["production_ranking"]["status"] == "out_of_scope"


async def test_graph_summary_is_bounded_and_missing_structures_are_explicit() -> None:
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test") as ac:
    graph = await ac.get("/materials/lemat-aln/graph-summary")
    missing = await ac.get("/materials/lemat-tialn-screen/graph-summary")

  assert graph.status_code == 200
  data = graph.json()
  assert data["material_id"] == "lemat-aln"
  assert len(data["nodes"]) == 4
  assert data["edge_count"] > 0
  assert data["node_feature_shape"] == [4, 103]
  assert len(data["edges"]) <= 96
  assert missing.status_code == 422
  assert "graph export excluded" in missing.json()["detail"]


async def test_audited_default_rank_is_stable_and_non_binary() -> None:
  transport = ASGITransport(app=app)
  request = {
    "objectives": {
      "density": {"direction": "minimize", "weight": 0.6},
      "bulk_modulus": {"direction": "maximize", "weight": 0.4},
    },
    "constraints": {
      "energy_above_hull": {"max": 0.025},
      "density": {"max": 6.0},
    },
    "missing": "worst",
  }
  async with AsyncClient(transport=transport, base_url="http://test") as ac:
    response = await ac.post("/scores/rank/audit", json=request)

  assert response.status_code == 200
  data = response.json()
  assert [row["material_id"] for row in data["ranked"]] == [
    "lemat-aln",
    "lemat-tin-beta",
    "lemat-tin-alpha",
  ]
  assert data["report"]["pool_size"] == 4
  assert data["report"]["ranked_count"] == 3
  assert data["report"]["excluded_by_constraints"] == 1
  assert data["report"]["binary_normalization"] is False
  assert data["report"]["effective_objectives"] == ["density", "bulk_modulus"]
