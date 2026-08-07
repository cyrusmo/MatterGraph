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

  assert data["graph_export"] == {"included_count": 3, "excluded_count": 1}
  assert 1 <= len(data["benchmark_preview"]) <= 3
  assert {"material_id", "formula", "target"} <= set(data["benchmark_preview"][0])
  assert data["provenance"] == {
    "fixture_path": "data/demo/lemat_bulk_sample.json",
    "loader": "LeMatBulk.from_records",
    "workflow_version": "v0.1",
    "run_id": "lematerial_bulk_demo_static_v0_1",
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
      json={"material_id": "demo-al-fcc-1"},
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
      json={"material_id": "demo-fe-bcc-1"},
    )
  assert r.status_code == 200
  data = r.json()
  assert data["status"] == "failed"
  assert data["result"] is None
  assert "does not support species: Fe" in data["error"]
