import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient

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
