from __future__ import annotations

from mattergraph.schema.material import Material


class OQMDStubConnector:
  """
  Placeholder for an Open Quantum Materials Database connector (network + schema
  to be fleshed out). This stub keeps the public API surface and docs stable.
  """

  def fetch(self, *args: object, **kwargs: object) -> list[Material]:  # noqa: ARG002
    return []
