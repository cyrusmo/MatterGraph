from __future__ import annotations

from typing import Any

import httpx
import pytest
from mattergraph.schema.material import Material
from mattergraph_connectors import NOMADConnector, NOMADStubConnector
from mattergraph_connectors.nomad import NOMADHTTPError, NOMADPayloadError


class FakeResponse:
  def __init__(self, payload: Any, *, status_code: int = 200) -> None:
    self.payload = payload
    self.status_code = status_code
    self.request = httpx.Request("POST", "https://nomad.test/entries/query")
    self.response = httpx.Response(status_code, request=self.request)

  def raise_for_status(self) -> None:
    if self.status_code >= 400:
      raise httpx.HTTPStatusError(
        f"HTTP {self.status_code}",
        request=self.request,
        response=self.response,
      )

  def json(self) -> Any:
    return self.payload


class FakeClient:
  def __init__(self, responses: list[FakeResponse] | None = None) -> None:
    self.responses = list(responses or [])
    self.calls: list[dict[str, Any]] = []
    self.closed = False

  def post(self, url: str, *, json: dict[str, Any]) -> FakeResponse:
    self.calls.append({"url": url, "json": json})
    if not self.responses:
      msg = "No fake response configured"
      raise AssertionError(msg)
    return self.responses.pop(0)

  def close(self) -> None:
    self.closed = True


def _row(entry_id: str, formula: str = "TiO2") -> dict[str, Any]:
  return {
    "entry_id": entry_id,
    "upload_id": f"upload-{entry_id}",
    "parser_name": "parsers/vasp",
    "results": {
      "material": {
        "chemical_formula_reduced": formula,
        "chemical_formula_hill": formula,
        "elements": ["Ti", "O"],
        "n_elements": 2,
      },
    },
  }


def _page(rows: list[dict[str, Any]], *, next_value: str | None = None) -> dict[str, Any]:
  pagination: dict[str, Any] = {
    "page_size": len(rows),
    "order_by": "entry_id",
    "order": "asc",
  }
  if next_value:
    pagination["next_page_after_value"] = next_value
  return {"data": rows, "pagination": pagination}


def test_nomad_connector_builds_public_element_query_payload() -> None:
  client = FakeClient([FakeResponse(_page([_row("a")]))])
  connector = NOMADConnector(base_url="https://nomad.test/api/v1", client=client)  # type: ignore[arg-type]

  materials = connector.fetch(elements=["Ti", "O"], max_records=1, page_size=25)

  assert len(materials) == 1
  call = client.calls[0]
  assert call["url"] == "https://nomad.test/api/v1/entries/query"
  payload = call["json"]
  assert payload["owner"] == "public"
  assert payload["query"] == {"results.material.elements": {"all": ["Ti", "O"]}}
  assert payload["pagination"] == {
    "page_size": 1,
    "order_by": "entry_id",
    "order": "asc",
  }
  assert payload["required"]["include"] == [
    "entry_id",
    "upload_id",
    "parser_name",
    "results.material.chemical_formula_reduced",
    "results.material.chemical_formula_hill",
    "results.material.elements",
    "results.material.n_elements",
  ]


def test_nomad_connector_paginates_with_after_value_and_truncates() -> None:
  client = FakeClient(
    [
      FakeResponse(_page([_row("a")], next_value="cursor-a")),
      FakeResponse(_page([_row("b"), _row("c")])),
    ]
  )
  connector = NOMADConnector(base_url="https://nomad.test/api/v1", client=client)  # type: ignore[arg-type]

  materials = connector.fetch(max_records=2, page_size=10)

  assert [material.material_id for material in materials] == ["nomad:a", "nomad:b"]
  assert client.calls[0]["json"]["pagination"]["page_size"] == 2
  assert "page_after_value" not in client.calls[0]["json"]["pagination"]
  assert client.calls[1]["json"]["pagination"]["page_after_value"] == "cursor-a"
  assert client.calls[1]["json"]["pagination"]["page_size"] == 1


def test_nomad_connector_maps_valid_rows_to_materials() -> None:
  client = FakeClient([FakeResponse(_page([_row("entry-1")]))])
  connector = NOMADConnector(client=client)  # type: ignore[arg-type]

  materials = connector.fetch(max_records=1)

  assert len(materials) == 1
  material = materials[0]
  assert isinstance(material, Material)
  assert material.material_id == "nomad:entry-1"
  assert material.formula == "TiO2"
  assert material.properties == []
  assert material.metadata["source"] == "nomad"
  assert material.metadata["entry_id"] == "entry-1"
  assert material.metadata["upload_id"] == "upload-entry-1"
  assert material.metadata["parser_name"] == "parsers/vasp"
  assert material.metadata["results_material"]["n_elements"] == 2


def test_nomad_connector_skips_malformed_rows_with_warning() -> None:
  malformed = _row("missing-formula")
  malformed["results"]["material"].pop("chemical_formula_reduced")
  malformed["results"]["material"].pop("chemical_formula_hill")
  client = FakeClient([FakeResponse(_page([malformed, _row("valid")]))])
  connector = NOMADConnector(client=client)  # type: ignore[arg-type]

  with pytest.warns(RuntimeWarning, match="missing material formula"):
    materials = connector.fetch(max_records=2)

  assert [material.material_id for material in materials] == ["nomad:valid"]


def test_nomad_connector_raises_for_http_failures() -> None:
  client = FakeClient([FakeResponse({"detail": "unavailable"}, status_code=503)])
  connector = NOMADConnector(client=client)  # type: ignore[arg-type]

  with pytest.raises(NOMADHTTPError, match="HTTP 503"):
    connector.fetch(max_records=1)


def test_nomad_connector_raises_for_malformed_page_payload() -> None:
  client = FakeClient([FakeResponse({"pagination": {}})])
  connector = NOMADConnector(client=client)  # type: ignore[arg-type]

  with pytest.raises(NOMADPayloadError, match="list data and object pagination"):
    connector.fetch(max_records=1)


def test_nomad_connector_does_not_close_injected_client() -> None:
  client = FakeClient([FakeResponse(_page([]))])
  connector = NOMADConnector(client=client)  # type: ignore[arg-type]

  connector.close()

  assert not client.closed


def test_nomad_context_manager_closes_owned_client(monkeypatch: pytest.MonkeyPatch) -> None:
  client = FakeClient([FakeResponse(_page([]))])

  def fake_client_factory(*args: Any, **kwargs: Any) -> FakeClient:  # noqa: ARG001
    return client

  monkeypatch.setattr("mattergraph_connectors.nomad.httpx.Client", fake_client_factory)

  with NOMADConnector() as connector:
    assert connector.fetch(max_records=1) == []

  assert client.closed


def test_nomad_stub_connector_keeps_backward_compatible_name() -> None:
  assert issubclass(NOMADStubConnector, NOMADConnector)
