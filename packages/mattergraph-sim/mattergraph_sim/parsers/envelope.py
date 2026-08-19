from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from mattergraph import SimulationResultEnvelope


def parse_result_envelope(
  payload: str | bytes | Mapping[str, Any],
) -> SimulationResultEnvelope:
  """Validate an external JSON result envelope without launching an engine."""
  if isinstance(payload, bytes):
    payload = payload.decode("utf-8")
  if isinstance(payload, str):
    value = json.loads(payload)
  else:
    value = dict(payload)
  if not isinstance(value, dict):
    msg = "simulation result envelope must be a JSON object"
    raise ValueError(msg)
  return SimulationResultEnvelope.model_validate(value)


__all__ = ["parse_result_envelope"]
