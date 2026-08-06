from __future__ import annotations

from typing import Any

from mattergraph.schema.material import Material

from mattergraph_connectors.base import ConnectorQuery

SOURCE_NAME = "oqmd"


class OQMDStubConnector:
  """
  Placeholder for an Open Quantum Materials Database connector.

  This deliberately raises rather than returning an empty list. An unimplemented connector
  that answers every query with ``[]`` is indistinguishable from a real one whose filter
  matched nothing, which is exactly how the JARVIS connector stayed dead for an unknown
  period. OQMD is reachable through OPTIMADE; prefer that route.
  """

  source_name = SOURCE_NAME

  def fetch(self, query: ConnectorQuery | None = None, **legacy: Any) -> list[Material]:  # noqa: ARG002
    msg = (
      "OQMDStubConnector is not implemented and returns no data. Query OQMD through its "
      "OPTIMADE endpoint instead. This raises rather than returning [] so an unimplemented "
      "connector is never mistaken for a query that matched nothing."
    )
    raise NotImplementedError(msg)


__all__ = ["OQMDStubConnector"]
