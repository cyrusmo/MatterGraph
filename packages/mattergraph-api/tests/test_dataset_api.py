import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from httpx import ASGITransport, AsyncClient
from mattergraph import DatasetManifest
from mattergraph_api.main import app
from mattergraph_api.services.dataset_registry import DatasetRegistry, dataset_registry

pytestmark = pytest.mark.asyncio


def _jsonl() -> str:
  records = [
    {
      "material_id": "local-aln",
      "formula": "AlN",
      "structure": {
        "lattice": [[3.11, 0, 0], [-1.555, 2.693, 0], [0, 0, 4.98]],
        "species": ["Al", "Al", "N", "N"],
        "coords": [
          [1 / 3, 2 / 3, 0],
          [2 / 3, 1 / 3, 0.5],
          [1 / 3, 2 / 3, 0.382],
          [2 / 3, 1 / 3, 0.882],
        ],
      },
      "properties": [
        {"name": "density", "value": 3.26, "unit": "g/cm^3", "source": "user"},
        {"name": "energy", "value": -7.1, "unit": "eV", "source": "user"},
      ],
    },
    {
      "material_id": "local-tin",
      "formula": "TiN",
      "properties": [
        {"name": "density", "value": 5.22, "unit": "g/cm^3", "source": "user"},
        {"name": "energy", "value": -8.0, "unit": "eV", "source": "user"},
      ],
    },
  ]
  return "".join(json.dumps(record) + "\n" for record in records)


async def test_local_dataset_flows_through_public_surfaces() -> None:
  dataset_registry.clear()
  transport = ASGITransport(app=app)
  content = _jsonl()
  async with AsyncClient(transport=transport, base_url="http://test") as client:
    inspection = await client.post(
      "/datasets/inspect",
      json={"filename": "contributor.jsonl", "format": "jsonl", "content": content},
    )
    imported = await client.post(
      "/datasets/import",
      json={"filename": "contributor.jsonl", "format": "jsonl", "content": content},
    )
    assert inspection.status_code == 200
    assert inspection.json()["row_count"] == 2
    assert imported.status_code == 200, imported.text
    dataset_id = imported.json()["dataset_id"]

    listing = await client.get("/datasets")
    detail = await client.get(f"/datasets/{dataset_id}")
    materials = await client.get("/materials", params={"dataset_id": dataset_id})
    search = await client.get("/search", params={"dataset_id": dataset_id, "element": "Al"})
    graph = await client.get(
      "/materials/local-aln/graph-summary", params={"dataset_id": dataset_id}
    )
    ranking = await client.post(
      "/scores/rank/audit",
      json={
        "dataset_id": dataset_id,
        "objectives": {"density": "minimize", "energy": "maximize"},
      },
    )
    sliced = await client.post(
      f"/datasets/{dataset_id}/slices/preview",
      json={"include_elements": ["Al", "N", "Ti"], "max_nelements": 2, "target": "energy"},
    )
    exported = await client.get(f"/datasets/{dataset_id}/export", params={"format": "jsonl"})

  assert listing.json()["registry"]["entry_count"] == 1
  assert detail.json()["normalized_bytes"] == len(exported.content)
  assert [material["material_id"] for material in materials.json()] == ["local-aln", "local-tin"]
  assert [material["material_id"] for material in search.json()] == ["local-aln"]
  assert graph.status_code == 200
  assert graph.json()["validation"]["reciprocal"] is True
  assert ranking.status_code == 200
  assert ranking.json()["report"]["ranked_count"] == 2
  assert sliced.status_code == 200, sliced.text
  assert sliced.json()["graph_readiness"] == {"included_count": 1, "excluded_count": 1}
  assert exported.headers["x-mattergraph-sha256"] == hashlib.sha256(exported.content).hexdigest()
  assert b"node_features" not in exported.content


async def test_strict_failure_and_degraded_import_are_explicit() -> None:
  dataset_registry.clear()
  content = "material_id,formula,density\na,AlN,3.26\nb,invalid,4.0\n"
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test") as client:
    strict = await client.post(
      "/datasets/import",
      json={"filename": "mixed.csv", "format": "csv", "content": content},
    )
    degraded = await client.post(
      "/datasets/import",
      json={
        "filename": "mixed.csv",
        "format": "csv",
        "content": content,
        "error_policy": "skip_invalid_rows",
      },
    )
  assert strict.status_code == 422
  assert strict.json()["report"]["status"] == "invalid"
  assert degraded.status_code == 200
  assert degraded.json()["manifest"]["degraded"] is True
  assert degraded.json()["accepted_count"] == 1


async def test_unknown_and_deleted_datasets_return_structured_404() -> None:
  dataset_registry.clear()
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test") as client:
    missing = await client.get("/datasets/mg_ds_missing")
    imported = await client.post(
      "/datasets/import",
      json={
        "filename": "one.jsonl",
        "format": "jsonl",
        "content": '{"material_id":"one","formula":"AlN"}\n',
      },
    )
    dataset_id = imported.json()["dataset_id"]
    deleted = await client.delete(f"/datasets/{dataset_id}")
    after = await client.get(f"/datasets/{dataset_id}")
  assert missing.status_code == 404
  assert missing.json()["code"] == "dataset_not_found"
  assert deleted.status_code == 200
  assert after.status_code == 404


async def test_registry_lru_byte_limits_and_materialization_coalescing() -> None:
  registry = DatasetRegistry(max_entries=2, max_bytes=2_000)

  def add(index: int) -> str:
    payload = f'{{"material_id":"m{index}","formula":"AlN"}}\n'.encode()
    digest = hashlib.sha256(payload).hexdigest()
    dataset_id = f"mg_ds_{digest[:16]}"
    registry.register(
      DatasetManifest(
        dataset_id=dataset_id,
        name=f"{index}.jsonl",
        format="jsonl",
        record_count=1,
        accepted_count=1,
        rejected_count=0,
        content_sha256=digest,
        normalized_sha256=digest,
        normalized_bytes=len(payload),
      ),
      payload,
    )
    return dataset_id

  first = add(1)
  second = add(2)
  registry.get(first)  # refresh first, making second the eviction victim
  third = add(3)
  assert [entry["manifest"]["dataset_id"] for entry in registry.list()] == [third, first]
  with pytest.raises(Exception, match="evicted dataset"):
    registry.get(second)

  with ThreadPoolExecutor(max_workers=2) as pool:
    stores = list(pool.map(registry.materialize, [third, third]))
  assert stores[0] is stores[1]
  registry.materialize(first)
  assert registry.active_dataset_id == first
