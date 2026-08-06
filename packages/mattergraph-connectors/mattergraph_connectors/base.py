"""The contract every MatterGraph connector implements.

Before this module the connector "interface" was a convention: a class with a ``fetch``
returning ``list[Material]``. Nothing enforced it, and the signatures had already drifted
four ways — Materials Project took ``material_ids``/``properties``/``num_chunks``/``chunk_size``,
JARVIS took ``max_records``, NOMAD took ``max_records``/``page_size``, and the OQMD stub took
``*args, **kwargs`` and ignored all of them. :class:`ConnectorQuery` gives those one shape and
:class:`Connector` makes conformance testable.
"""

from __future__ import annotations

import warnings
from typing import Any, Protocol, runtime_checkable

from mattergraph.normalization.properties import canonical_property_name
from mattergraph.schema.material import Material
from mattergraph.schema.property import PropertyMethod
from mattergraph.schema.provenance import ProvenanceRecord
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Legacy keyword names accepted by the pre-contract fetch() signatures, mapped onto their
# ConnectorQuery field. Callers using these get a DeprecationWarning, not a break.
_LEGACY_ALIASES: dict[str, str] = {
  "material_ids": "source_ids",
  "chunk_size": "page_size",
}


class ConnectorQuery(BaseModel):
  """A source-independent description of what to fetch.

  Every field is a *request*, not a guarantee: a connector that cannot honor one must say so
  by raising, never by silently ignoring it.
  """

  model_config = ConfigDict(extra="forbid", validate_assignment=True)

  elements: list[str] | None = Field(
    default=None,
    description="Restrict to records containing these element symbols",
  )
  source_ids: list[str] | None = Field(
    default=None,
    description="Fetch these upstream identifiers directly, e.g. mp-149 or JVASP-1002",
  )
  properties: list[str] | None = Field(
    default=None,
    description="Canonical property names to return; connectors that cannot filter must raise",
  )
  max_records: int = Field(default=50, description="Upper bound on returned materials")
  page_size: int = Field(default=25, description="Records per upstream request where paged")

  @field_validator("elements", "source_ids", "properties")
  @classmethod
  def _clean_list(cls, value: list[str] | None) -> list[str] | None:
    if value is None:
      return None
    cleaned = [item.strip() for item in value if str(item).strip()]
    return cleaned or None

  @field_validator("max_records", "page_size")
  @classmethod
  def _positive(cls, value: int, info: Any) -> int:
    if value < 1:
      msg = f"{info.field_name} must be at least 1"
      raise ValueError(msg)
    return value


@runtime_checkable
class Connector(Protocol):
  """A source of :class:`Material` records.

  ``isinstance(obj, Connector)`` checks that the members exist, not that their signatures
  match — see ``tests/test_connector_contract.py``, which also exercises the call itself.
  """

  source_name: str

  def fetch(self, query: ConnectorQuery | None = None, **legacy: Any) -> list[Material]:
    """Return at most ``query.max_records`` materials matching ``query``."""
    ...


def coerce_query(
  query: ConnectorQuery | None,
  legacy: dict[str, Any],
  *,
  source_name: str,
) -> ConnectorQuery:
  """Accept either a :class:`ConnectorQuery` or the pre-contract keyword form.

  The keyword form is kept working because ``scripts/ingest_*.py`` and ``examples/`` use it;
  it warns rather than breaking. Passing both forms at once is a caller bug and raises.
  """
  if query is not None and legacy:
    msg = (
      f"{source_name}.fetch() got both a ConnectorQuery and keyword arguments "
      f"({', '.join(sorted(legacy))}); pass one or the other"
    )
    raise TypeError(msg)
  if query is not None:
    return query
  if not legacy:
    return ConnectorQuery()

  warnings.warn(
    f"Calling {source_name}.fetch() with keyword arguments is deprecated; "
    f"pass a ConnectorQuery instead, e.g. fetch(ConnectorQuery(elements=['Ti'])).",
    DeprecationWarning,
    stacklevel=3,
  )
  mapped: dict[str, Any] = {}
  for key, value in legacy.items():
    field = _LEGACY_ALIASES.get(key, key)
    if field not in ConnectorQuery.model_fields:
      msg = f"{source_name}.fetch() got an unexpected keyword argument {key!r}"
      raise TypeError(msg)
    if value is not None:
      mapped[field] = value
  return ConnectorQuery(**mapped)


def apply_property_filter(
  materials: list[Material],
  query: ConnectorQuery,
  *,
  supported: frozenset[str],
  source_name: str,
) -> list[Material]:
  """Restrict each material to the requested properties, or raise if it cannot be done.

  A connector that accepts ``properties`` and returns everything anyway is the failure this
  guards against: the caller has no way to tell that the filter did nothing.
  """
  if not query.properties:
    return materials

  requested = {canonical_property_name(name) for name in query.properties}
  unsupported = sorted(requested - supported)
  if unsupported:
    msg = (
      f"{source_name} cannot return {', '.join(unsupported)}; "
      f"supported properties are {', '.join(sorted(supported))}"
    )
    raise ValueError(msg)

  for material in materials:
    material.properties = [p for p in material.properties if p.name in requested]
  return materials


def connector_provenance(
  source: str,
  *,
  source_id: str | None = None,
  method: PropertyMethod = PropertyMethod.DFT,
  notes: str | None = None,
  parameters: dict[str, Any] | None = None,
) -> ProvenanceRecord:
  """Build the lineage record every ingested material carries.

  ``constraint.provenance`` asks that a value say where it came from. Connectors previously
  put lineage in ``Material.metadata``, which is untyped and invisible to anything that
  reasons about provenance, leaving ``Material.provenance`` empty on every ingested record.
  """
  return ProvenanceRecord(
    source=source,
    method=method,
    source_id=source_id,
    notes=notes,
    parameters=parameters,
  )


__all__ = [
  "Connector",
  "ConnectorQuery",
  "apply_property_filter",
  "coerce_query",
  "connector_provenance",
]
