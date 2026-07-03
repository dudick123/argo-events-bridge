"""Unit tests for the Akuity API client (HTTP behavior via respx)."""

import httpx
import pytest
import respx

from bridge.clients.akuity import AkuityClient, operation_key
from bridge.config import AkuitySettings
from bridge.metrics import Metrics
from conftest import make_app_payload

BASE = "http://akuity.test"
APPS_PATH = "/api/v1/orgs/o/instances/i/applications"


def make_client(metrics: Metrics) -> AkuityClient:
    settings = AkuitySettings(
        base_url=BASE, org_id="o", instance_id="i", api_key="k", max_retries=2
    )
    return AkuityClient(settings, metrics)


@respx.mock
async def test_list_applications_parses_items_and_sends_selector(metrics: Metrics) -> None:
    route = respx.get(f"{BASE}{APPS_PATH}").respond(
        200, json={"items": [make_app_payload(phase="Running")]}
    )
    client = make_client(metrics)
    apps = await client.list_applications()

    assert len(apps) == 1
    assert apps[0].metadata.name == "my-app"
    op_state = apps[0].operation_state
    assert op_state is not None
    assert op_state.phase == "Running"
    assert op_state.initiated_by_username == "test.user@org.com"
    request = route.calls[0].request
    assert request.url.params["selector"] == "env=prod"
    assert request.headers["Authorization"] == "Bearer k"


@respx.mock
async def test_list_applications_handles_empty_items(metrics: Metrics) -> None:
    respx.get(f"{BASE}{APPS_PATH}").respond(200, json={"items": None})
    client = make_client(metrics)
    assert await client.list_applications() == []


@respx.mock
async def test_rate_limited_then_success_retries(metrics: Metrics) -> None:
    route = respx.get(f"{BASE}{APPS_PATH}")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"items": []}),
    ]
    client = make_client(metrics)
    assert await client.list_applications() == []
    assert route.call_count == 2


@respx.mock
async def test_persistent_failure_raises_after_retries(metrics: Metrics) -> None:
    route = respx.get(f"{BASE}{APPS_PATH}").respond(500)
    client = make_client(metrics)
    with pytest.raises(RuntimeError, match="failed after retries"):
        await client.list_applications()
    assert route.call_count == 3  # initial + 2 retries


def test_operation_key_is_deterministic_and_distinct() -> None:
    key1 = operation_key("my-app", "2026-07-02T14:30:00Z", "def5678")
    key2 = operation_key("my-app", "2026-07-02T14:30:00Z", "def5678")
    key3 = operation_key("my-app", "2026-07-02T14:38:00Z", "def5678")
    assert key1 == key2
    assert key1 != key3
    assert key1.startswith("sha256:")
