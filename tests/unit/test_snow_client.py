"""Unit tests for the SNOW CR API client (HTTP behavior via respx)."""

import httpx
import respx

from bridge.clients.snow import SnowClient
from bridge.config import SnowSettings
from bridge.metrics import Metrics

BASE = "http://snow.test"


def make_client(metrics: Metrics) -> SnowClient:
    settings = SnowSettings(base_url=BASE, api_key="k", max_retries=2, retry_backoff_base_ms=1)
    return SnowClient(settings, metrics)


@respx.mock
async def test_create_and_start_returns_sys_id(metrics: Metrics) -> None:
    respx.post(f"{BASE}/api/change").respond(
        201, json={"sys_id": "abc123", "number": "CHG0012345"}
    )
    client = make_client(metrics)
    sys_id = await client.create_and_start({"correlation_id": "sha256:x"})
    assert sys_id == "abc123"


@respx.mock
async def test_duplicate_correlation_id_409_is_treated_as_success(metrics: Metrics) -> None:
    respx.post(f"{BASE}/api/change").respond(409, json={"sys_id": "existing-1"})
    client = make_client(metrics)
    sys_id = await client.create_and_start({"correlation_id": "sha256:x"})
    assert sys_id == "existing-1"


@respx.mock
async def test_client_error_4xx_is_not_retried(metrics: Metrics) -> None:
    route = respx.post(f"{BASE}/api/change").respond(400, json={"error": "missing field"})
    client = make_client(metrics)
    assert await client.create_and_start({"bad": "payload"}) is None
    assert route.call_count == 1


@respx.mock
async def test_server_error_retries_then_gives_up(metrics: Metrics) -> None:
    route = respx.post(f"{BASE}/api/change").respond(503)
    client = make_client(metrics)
    assert await client.create_and_start({"correlation_id": "sha256:x"}) is None
    assert route.call_count == 3  # initial + 2 retries


@respx.mock
async def test_server_error_then_success_recovers(metrics: Metrics) -> None:
    route = respx.post(f"{BASE}/api/change")
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(201, json={"sys_id": "abc123"}),
    ]
    client = make_client(metrics)
    assert await client.create_and_start({"correlation_id": "sha256:x"}) == "abc123"


@respx.mock
async def test_close_successful_sends_result_field(metrics: Metrics) -> None:
    route = respx.patch(f"{BASE}/api/change/abc123/close").respond(200, json={})
    client = make_client(metrics)
    assert await client.close_successful("abc123", {"close_notes": "ok"}) is True
    body = route.calls[0].request.content
    assert b'"result": "successful"' in body or b'"result":"successful"' in body


@respx.mock
async def test_close_unsuccessful_sends_result_field(metrics: Metrics) -> None:
    route = respx.patch(f"{BASE}/api/change/abc123/close").respond(200, json={})
    client = make_client(metrics)
    assert await client.close_unsuccessful("abc123", {"close_notes": "bad"}) is True
    body = route.calls[0].request.content
    assert b"unsuccessful" in body


@respx.mock
async def test_attach_audit_posts_document(metrics: Metrics) -> None:
    route = respx.post(f"{BASE}/api/change/abc123/audit").respond(
        201, json={"attachment_id": "xyz"}
    )
    client = make_client(metrics)
    assert await client.attach_audit("abc123", {"operation_key": "sha256:x"}) is True
    assert route.call_count == 1
