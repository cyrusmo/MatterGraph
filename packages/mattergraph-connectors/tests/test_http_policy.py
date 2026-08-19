import httpx
import pytest
from mattergraph_connectors.http_policy import (
  ConnectorHTTPPolicy,
  MemoryResponseCache,
  request_with_policy,
)


def test_retries_retry_after_and_stops_at_bound(monkeypatch: pytest.MonkeyPatch) -> None:
  attempts = 0
  sleeps: list[float] = []

  def handler(request: httpx.Request) -> httpx.Response:
    nonlocal attempts
    attempts += 1
    if attempts < 3:
      return httpx.Response(429, headers={"Retry-After": "0.01"}, request=request)
    return httpx.Response(200, json={"ok": True}, request=request)

  monkeypatch.setattr("mattergraph_connectors.http_policy.time.sleep", sleeps.append)
  client = httpx.Client(transport=httpx.MockTransport(handler))
  response = request_with_policy(
    client,
    "GET",
    "https://example.test/data",
    policy=ConnectorHTTPPolicy(max_retries=2),
  )
  assert response.json() == {"ok": True}
  assert attempts == 3
  assert sleeps == [0.01, 0.01]


def test_get_cache_is_explicit_and_bounded() -> None:
  attempts = 0

  def handler(request: httpx.Request) -> httpx.Response:
    nonlocal attempts
    attempts += 1
    return httpx.Response(200, json={"attempt": attempts}, request=request)

  client = httpx.Client(transport=httpx.MockTransport(handler))
  policy = ConnectorHTTPPolicy(max_retries=0)
  cache = MemoryResponseCache(max_entries=1)
  first = request_with_policy(client, "GET", "https://example.test/a", policy=policy, cache=cache)
  second = request_with_policy(client, "GET", "https://example.test/a", policy=policy, cache=cache)
  request_with_policy(client, "GET", "https://example.test/b", policy=policy, cache=cache)
  request_with_policy(client, "GET", "https://example.test/a", policy=policy, cache=cache)
  assert first.json() == second.json()
  assert attempts == 3
