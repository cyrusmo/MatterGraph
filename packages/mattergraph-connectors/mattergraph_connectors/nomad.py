from __future__ import annotations

from mattergraph.schema.material import Material


class NOMADStubConnector:
  """
  NOMAD is powerful but more complex; start with a stub that documents intent.
  """

  def fetch(self, *args: object, **kwargs: object) -> list[Material]:  # noqa: ARG002
    return []
