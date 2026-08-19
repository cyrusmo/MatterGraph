import json
import time

import pytest
from httpx import ASGITransport, AsyncClient
from mattergraph_api.main import app

pytestmark = pytest.mark.asyncio


async def test_health_does_not_materialize_demo(monkeypatch: pytest.MonkeyPatch) -> None:
  def unexpected_demo_work(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("health endpoint invoked demo materialization or graph work")

  monkeypatch.setattr(
    "mattergraph_api.services.store_service.get_store",
    unexpected_demo_work,
  )
  monkeypatch.setattr(
    "mattergraph_api.routes.demo.graph_summary",
    unexpected_demo_work,
  )
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
  assert data["source_subset"] == "compatible_pbe"
  assert data["schema_report"]["row_count"] == 24

  candidate_slice = data["candidate_slice"]
  assert candidate_slice["slice_id"].startswith("mg_slice_")
  assert candidate_slice["slice_name"] == "spc_tialn_candidates_v1"
  assert candidate_slice["target"] == "energy_above_hull"
  assert candidate_slice["input_count"] == 24
  assert candidate_slice["output_count"] == 24
  assert candidate_slice["removed_count"] == 0
  assert [step["name"] for step in candidate_slice["filter_steps"]] == [
    "filter_elements",
    "filter_complexity",
  ]

  assert data["graph_export"]["included_count"] == 24
  assert data["graph_export"]["excluded_count"] == 0
  assert len(data["graph_export"]["previews"]) == 24
  assert data["candidate_slice"]["report"]["deduplication_basis"] == "structure_fingerprint"
  assert data["benchmark"]["target"] == "energy_above_hull"
  assert data["benchmark"]["row_count"] == 24
  assert 1 <= len(data["benchmark_preview"]) <= 3
  assert {"material_id", "formula", "target"} <= set(data["benchmark_preview"][0])
  provenance = data["provenance"]
  assert provenance["fixture_path"] == "data/demo/spc_real_snapshot.json"
  assert provenance["workflow_version"] == "v1.0"
  assert provenance["fixture_kind"] == "checksummed_real_snapshot"
  assert provenance["license"] == "CC-BY-4.0"
  assert provenance["citation_doi"] == "10.57967/hf/3762"
  assert len(provenance["snapshot_sha256"]) == 64

  serialized = json.dumps(data)
  assert "graphs" not in data
  assert "node_features" not in serialized
  assert "edge_index" not in serialized


async def test_simulation_relax_succeeds_for_supported_demo_material() -> None:
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test") as ac:
    r = await ac.post(
      "/simulations/ase/relax",
      json={"material_id": "agm003273599"},
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
      json={"material_id": "agm002163329"},
    )
  assert r.status_code == 200
  data = r.json()
  assert data["status"] == "failed"
  assert data["result"] is None
  assert "does not support species: Ti" in data["error"]


async def test_demo_preflight_is_ready_and_coherent() -> None:
  transport = ASGITransport(app=app)
  started = time.perf_counter()
  async with AsyncClient(transport=transport, base_url="http://test") as ac:
    response = await ac.get("/demo/preflight")
  elapsed = time.perf_counter() - started

  assert response.status_code == 200
  data = response.json()
  assert data["status"] == "ready"
  assert elapsed < 3
  assert data["record_count"] == 24
  assert data["graph"] == {
    "included_count": 24,
    "excluded_count": 0,
    "invalid_count": 0,
    "validation_state": "valid",
  }
  assert data["ranking"]["ranked_count"] == 6
  assert data["ranking"]["excluded_by_constraints"] == 18
  assert data["ranking"]["binary_normalization"] is False
  assert data["default_material_id"] == "agm003273599"
  assert data["fixture"]["snapshot_sha256"] == (
    "e1a925b5b047b9fc3d4172b7647c23de656f7422e990234c343dcbb9fa333c14"
  )
  assert data["fixture"]["upstream_revision"] == "0dc17eea904b860ad7288141e9870f67f8e6bb2c"
  assert data["chgnet"]["state"] == "cached_only"
  assert data["chgnet"]["reference_material_id"] == data["default_material_id"]


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
    graph = await ac.get("/materials/agm003273599/graph-summary")
    missing = await ac.get("/materials/not-a-real-id/graph-summary")

  assert graph.status_code == 200
  data = graph.json()
  assert data["material_id"] == "agm003273599"
  assert len(data["nodes"]) == 2
  assert data["edge_count"] > 0
  assert data["node_feature_shape"] == [2, 103]
  assert len(data["edges"]) <= 256
  assert data["validation"]["reciprocal"] is True
  assert data["validation"]["zero_distance_edges"] == 0
  assert data["validation"]["displacement_consistent"] is True
  assert data["validation"]["symmetry"] == {
    "status": "determined",
    "spacegroup_number": 216,
  }
  assert data["coordination_numbers"] == [4, 4]
  assert len(json.dumps(data).encode()) < 256 * 1024
  serialized = json.dumps(data)
  assert "node_features" not in serialized
  assert "edge_index" not in serialized
  assert missing.status_code == 404


async def test_audited_default_rank_is_stable_and_non_binary() -> None:
  transport = ASGITransport(app=app)
  request = {
    "objectives": {
      "density": {"direction": "minimize", "weight": 0.6},
      "energy_above_hull": {"direction": "minimize", "weight": 0.4},
    },
    "constraints": {
      "energy_above_hull": {"max": 0.05},
      "max_force": {"max": 0.2},
    },
    "missing": "worst",
  }
  async with AsyncClient(transport=transport, base_url="http://test") as ac:
    response = await ac.post("/scores/rank/audit", json=request)

  assert response.status_code == 200
  data = response.json()
  assert [row["material_id"] for row in data["ranked"]] == [
    "agm003273599",
    "agm004462854",
    "agm003220445",
    "agm005708132",
    "agm005543670",
    "agm002163329",
  ]
  assert data["report"]["pool_size"] == 24
  assert data["report"]["ranked_count"] == 6
  assert data["report"]["excluded_by_constraints"] == 18
  assert data["report"]["binary_normalization"] is False
  assert data["report"]["effective_objectives"] == ["density", "energy_above_hull"]
  assert all(isinstance(row["max_force"], float) for row in data["ranked"])


async def test_chgnet_reference_is_explicit_cached_evidence_and_compact() -> None:
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test") as ac:
    response = await ac.get("/simulations/chgnet/reference/agm003273599")
    missing = await ac.get("/simulations/chgnet/reference/agm002163329")

  assert response.status_code == 200
  data = response.json()
  assert data["label"] == "cached_reference"
  assert data["model"]["version"] == "0.3.0"
  assert len(data["model"]["weight_checksum"]) == 64
  assert data["result"]["converged"] is True
  assert len(data["result"]["trajectory"]) <= 128
  assert "not a DFT or experimental measurement" in data["scientific_boundary"]
  assert len(response.content) < 512 * 1024
  assert missing.status_code == 404
