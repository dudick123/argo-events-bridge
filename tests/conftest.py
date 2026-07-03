"""Shared fixtures: fake Redis, fake SNOW client, and app payload factory."""

from typing import Any

import fakeredis.aioredis
import pytest

from bridge.metrics import Metrics
from bridge.state import StateStore


def make_app_payload(
    name: str = "my-app",
    phase: str | None = "Running",
    revision: str = "def5678",
    started_at: str = "2026-07-02T14:30:00Z",
    finished_at: str | None = None,
    health: str = "Healthy",
    history: list[dict[str, Any]] | None = None,
    username: str = "test.user@org.com",
    automated: bool = False,
    resources: list[dict[str, Any]] | None = None,
    message: str = "",
) -> dict[str, Any]:
    """Build an Akuity Application payload like docs/akuity-api-examples.md.

    phase=None produces an idle app with no operationState.
    """
    operation_state: dict[str, Any] | None = None
    if phase is not None:
        sync_result: dict[str, Any] | None = None
        if phase in {"Succeeded", "Failed", "Error"}:
            sync_result = {"revision": revision, "resources": resources or []}
        operation_state = {
            "operation": {
                "sync": {"revision": revision},
                "initiatedBy": {"username": username, "automated": automated},
            },
            "phase": phase,
            "message": message,
            "syncResult": sync_result,
            "startedAt": started_at,
            "finishedAt": finished_at,
        }

    return {
        "metadata": {"name": name, "labels": {"env": "prod"}},
        "spec": {
            "project": "my-tenant",
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": "my-namespace",
            },
        },
        "status": {
            "sync": {"status": "Synced", "revision": revision},
            "health": {"status": health},
            "operationState": operation_state,
            "history": history or [],
        },
    }


class FakeSnow:
    """In-memory SNOW client satisfying SnowClientProtocol, recording calls."""

    def __init__(self) -> None:
        self.creates: list[tuple[str, dict[str, Any]]] = []
        self.closes: list[tuple[str, str, dict[str, Any]]] = []
        self.audits: list[tuple[str, dict[str, Any]]] = []
        self._counter = 0
        self.fail_creates = False

    async def create_and_start(self, payload: dict[str, Any]) -> str | None:
        if self.fail_creates:
            return None
        self._counter += 1
        sys_id = f"sys-{self._counter}"
        self.creates.append((sys_id, payload))
        return sys_id

    async def close_successful(self, cr_sys_id: str, payload: dict[str, Any]) -> bool:
        self.closes.append((cr_sys_id, "successful", payload))
        return True

    async def close_unsuccessful(self, cr_sys_id: str, payload: dict[str, Any]) -> bool:
        self.closes.append((cr_sys_id, "unsuccessful", payload))
        return True

    async def attach_audit(self, cr_sys_id: str, audit: dict[str, Any]) -> bool:
        self.audits.append((cr_sys_id, audit))
        return True


@pytest.fixture
def redis_client() -> fakeredis.aioredis.FakeRedis:
    """Async fake Redis with string decoding, matching production config."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def state(redis_client: fakeredis.aioredis.FakeRedis) -> StateStore:
    """StateStore backed by fake Redis."""
    return StateStore(redis_client, key_ttl_seconds=86400)


@pytest.fixture
def metrics() -> Metrics:
    """Real Metrics instance; DogStatsD UDP emission is fire-and-forget."""
    return Metrics(host="localhost", port=8125, service_name="test", env="test")


@pytest.fixture
def snow() -> FakeSnow:
    """Recording fake SNOW client."""
    return FakeSnow()
