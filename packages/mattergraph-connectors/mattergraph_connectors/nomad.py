from __future__ import annotations

import warnings
from types import TracebackType
from typing import Any

import httpx
from mattergraph.schema.material import Material

NOMAD_BASE_URL = "https://nomad-lab.eu/prod/v1/api/v1"

_REQUIRED_FIELDS = [
  "entry_id",
  "upload_id",
  "parser_name",
  "results.material.chemical_formula_reduced",
  "results.material.chemical_formula_hill",
  "results.material.elements",
  "results.material.n_elements",
]


class NOMADConnectorError(Exception):
  """Base exception for NOMAD connector failures."""


class NOMADHTTPError(NOMADConnectorError):
  """Raised when NOMAD cannot be reached or returns an HTTP error."""


class NOMADPayloadError(NOMADConnectorError):
  """Raised when a NOMAD response does not match the expected page shape."""


class NOMADMappingError(NOMADConnectorError):
  """Raised when a NOMAD entry cannot be mapped into a MatterGraph material."""


class NOMADConnector:
  """Read public NOMAD entry metadata and normalize it to MatterGraph materials."""

  def __init__(
    self,
    *,
    base_url: str = NOMAD_BASE_URL,
    timeout: float = 30.0,
    client: httpx.Client | None = None,
  ) -> None:
    self.base_url = base_url.rstrip("/")
    self._owns_client = client is None
    self._client = client or httpx.Client(timeout=timeout)

  def __enter__(self) -> NOMADConnector:
    return self

  def __exit__(
    self,
    exc_type: type[BaseException] | None,
    exc: BaseException | None,
    traceback: TracebackType | None,
  ) -> None:
    self.close()

  def close(self) -> None:
    if self._owns_client:
      self._client.close()

  def fetch(
    self,
    elements: list[str] | None = None,
    *,
    max_records: int = 50,
    page_size: int = 25,
  ) -> list[Material]:
    if max_records <= 0:
      return []
    if page_size <= 0:
      msg = "page_size must be positive"
      raise ValueError(msg)

    out: list[Material] = []
    page_after_value: str | None = None
    normalized_elements = _normalize_elements(elements)

    while len(out) < max_records:
      payload = _query_payload(
        elements=normalized_elements,
        page_size=min(page_size, max_records - len(out)),
        page_after_value=page_after_value,
      )
      page = self._post_entries_query(payload)
      rows = page["data"]
      if not rows:
        break

      for row in rows:
        if len(out) >= max_records:
          break
        material = _safe_row_to_material(row)
        if material is not None:
          out.append(material)

      page_after_value = page["pagination"].get("next_page_after_value")
      if not page_after_value:
        break

    return out

  def _post_entries_query(self, payload: dict[str, Any]) -> dict[str, Any]:
    try:
      response = self._client.post(f"{self.base_url}/entries/query", json=payload)
      response.raise_for_status()
    except httpx.HTTPStatusError as exc:
      status = exc.response.status_code
      msg = f"NOMAD entries/query failed with HTTP {status}"
      raise NOMADHTTPError(msg) from exc
    except httpx.RequestError as exc:
      msg = f"NOMAD entries/query request failed: {exc}"
      raise NOMADHTTPError(msg) from exc

    try:
      page = response.json()
    except ValueError as exc:
      msg = "NOMAD entries/query returned invalid JSON"
      raise NOMADPayloadError(msg) from exc

    if not isinstance(page, dict):
      msg = "NOMAD entries/query response must be a JSON object"
      raise NOMADPayloadError(msg)
    if not isinstance(page.get("data"), list) or not isinstance(page.get("pagination"), dict):
      msg = "NOMAD entries/query response must include list data and object pagination"
      raise NOMADPayloadError(msg)
    return page


class NOMADStubConnector(NOMADConnector):
  """Backward-compatible NOMAD name; prefer :class:`NOMADConnector` for new code."""


def _query_payload(
  *,
  elements: list[str] | None,
  page_size: int,
  page_after_value: str | None,
) -> dict[str, Any]:
  payload: dict[str, Any] = {
    "owner": "public",
    "query": {},
    "pagination": {
      "page_size": page_size,
      "order_by": "entry_id",
      "order": "asc",
    },
    "required": {
      "include": _REQUIRED_FIELDS,
    },
  }
  if elements:
    payload["query"] = {
      "results.material.elements": {
        "all": elements,
      },
    }
  if page_after_value:
    payload["pagination"]["page_after_value"] = page_after_value
  return payload


def _normalize_elements(elements: list[str] | None) -> list[str] | None:
  if not elements:
    return None
  normalized = [element.strip() for element in elements if element.strip()]
  return normalized or None


def _safe_row_to_material(row: Any) -> Material | None:
  try:
    return _row_to_material(row)
  except NOMADMappingError as exc:
    warnings.warn(str(exc), RuntimeWarning, stacklevel=2)
    return None


def _row_to_material(row: Any) -> Material:
  if not isinstance(row, dict):
    msg = "Skipping NOMAD row: row must be an object"
    raise NOMADMappingError(msg)

  entry_id = _clean_string(row.get("entry_id"))
  if entry_id is None:
    msg = "Skipping NOMAD row: missing entry_id"
    raise NOMADMappingError(msg)

  material_metadata = _material_metadata(row)
  formula = _clean_string(material_metadata.get("chemical_formula_reduced")) or _clean_string(
    material_metadata.get("chemical_formula_hill")
  )
  if formula is None:
    msg = f"Skipping NOMAD row {entry_id}: missing material formula"
    raise NOMADMappingError(msg)

  elements = material_metadata.get("elements")
  element_list = (
    [str(element).strip() for element in elements if str(element).strip()]
    if isinstance(elements, list)
    else []
  )

  try:
    return Material(
      material_id=f"nomad:{entry_id}",
      formula=formula,
      elements=element_list,
      properties=[],
      metadata={
        "source": "nomad",
        "entry_id": entry_id,
        "upload_id": row.get("upload_id"),
        "parser_name": row.get("parser_name"),
        "results_material": material_metadata,
      },
    )
  except Exception as exc:  # noqa: BLE001
    msg = f"Skipping NOMAD row {entry_id}: could not map material ({exc})"
    raise NOMADMappingError(msg) from exc


def _material_metadata(row: dict[str, Any]) -> dict[str, Any]:
  results = row.get("results")
  if not isinstance(results, dict):
    return {}
  material = results.get("material")
  if not isinstance(material, dict):
    return {}
  return dict(material)


def _clean_string(value: Any) -> str | None:
  if value is None:
    return None
  cleaned = str(value).strip()
  return cleaned or None


__all__ = [
  "NOMADConnector",
  "NOMADConnectorError",
  "NOMADHTTPError",
  "NOMADMappingError",
  "NOMADPayloadError",
  "NOMADStubConnector",
]
