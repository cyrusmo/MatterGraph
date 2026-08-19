from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field


class ConnectorHTTPPolicy(BaseModel):
  """Shared, bounded transport policy for public connector clients."""

  model_config = ConfigDict(extra="forbid", frozen=True)

  timeout_seconds: float = Field(default=30.0, gt=0, le=120)
  max_retries: int = Field(default=2, ge=0, le=5)
  backoff_seconds: float = Field(default=0.25, ge=0, le=5)
  max_retry_after_seconds: float = Field(default=10.0, ge=0, le=60)
  retry_statuses: frozenset[int] = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class CachedHTTPResponse:
  status_code: int
  headers: dict[str, str]
  content: bytes


class ResponseCache(Protocol):
  def get(self, key: str) -> CachedHTTPResponse | None: ...

  def put(self, key: str, response: CachedHTTPResponse) -> None: ...


class MemoryResponseCache:
  """Opt-in, process-local LRU cache; connector responses are never cached by default."""

  def __init__(self, max_entries: int = 32) -> None:
    if max_entries < 1:
      msg = "max_entries must be positive"
      raise ValueError(msg)
    self.max_entries = max_entries
    self._entries: OrderedDict[str, CachedHTTPResponse] = OrderedDict()

  def get(self, key: str) -> CachedHTTPResponse | None:
    response = self._entries.get(key)
    if response is not None:
      self._entries.move_to_end(key)
    return response

  def put(self, key: str, response: CachedHTTPResponse) -> None:
    self._entries[key] = response
    self._entries.move_to_end(key)
    while len(self._entries) > self.max_entries:
      self._entries.popitem(last=False)


def request_with_policy(
  client: httpx.Client,
  method: str,
  url: str,
  *,
  policy: ConnectorHTTPPolicy,
  cache: ResponseCache | None = None,
  **kwargs: Any,
) -> httpx.Response:
  """Execute one request with bounded retries, Retry-After, and opt-in GET caching."""
  normalized_method = method.upper()
  if not hasattr(client, "build_request"):
    # Preserve compatibility with lightweight injected clients used by contributors
    # and downstream tests. Real httpx clients take the bounded policy path below.
    operation = getattr(client, normalized_method.lower())
    return operation(url, **kwargs)
  kwargs.setdefault("timeout", policy.timeout_seconds)
  request = client.build_request(normalized_method, url, **kwargs)
  cache_key = _cache_key(request) if cache is not None and normalized_method == "GET" else None
  if cache is not None and cache_key is not None:
    cached = cache.get(cache_key)
    if cached is not None:
      return httpx.Response(
        cached.status_code,
        headers=cached.headers,
        content=cached.content,
        request=request,
      )

  last_error: httpx.RequestError | None = None
  for attempt in range(policy.max_retries + 1):
    try:
      response = client.send(request)
      if response.status_code not in policy.retry_statuses or attempt >= policy.max_retries:
        if cache is not None and cache_key is not None and response.is_success:
          cache.put(
            cache_key,
            CachedHTTPResponse(
              status_code=response.status_code,
              headers=dict(response.headers),
              content=response.content,
            ),
          )
        return response
      _sleep_before_retry(response, attempt, policy)
    except httpx.RequestError as error:
      last_error = error
      if attempt >= policy.max_retries:
        raise
      time.sleep(min(policy.backoff_seconds * (2**attempt), policy.max_retry_after_seconds))

  if last_error is not None:
    raise last_error
  msg = "connector HTTP policy exhausted without a response"
  raise RuntimeError(msg)


def _sleep_before_retry(
  response: httpx.Response,
  attempt: int,
  policy: ConnectorHTTPPolicy,
) -> None:
  retry_after = response.headers.get("Retry-After")
  delay = policy.backoff_seconds * (2**attempt)
  if retry_after:
    try:
      delay = max(0.0, float(retry_after))
    except ValueError:
      pass
  time.sleep(min(delay, policy.max_retry_after_seconds))


def _cache_key(request: httpx.Request) -> str:
  body = request.content.decode("utf-8", errors="replace") if request.content else ""
  headers = {
    key.lower(): value
    for key, value in request.headers.items()
    if key.lower() in {"accept", "content-type"}
  }
  payload = json.dumps(
    {
      "method": request.method,
      "url": str(request.url),
      "body": body,
      "headers": headers,
    },
    sort_keys=True,
    separators=(",", ":"),
  ).encode()
  return hashlib.sha256(payload).hexdigest()


__all__ = [
  "CachedHTTPResponse",
  "ConnectorHTTPPolicy",
  "MemoryResponseCache",
  "ResponseCache",
  "request_with_policy",
]
