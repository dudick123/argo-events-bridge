"""End-to-end CR lifecycle tests through the Poller (fake Akuity + SNOW)."""

from typing import Any

import pytest

from bridge.clients.akuity import Application
from bridge.config import AkuitySettings, RedisSettings, Settings, SnowSettings
from bridge.lifecycle import CRLifecycle
from bridge.metrics import Metrics
from bridge.poller import Poller
from bridge.stabilization import StabilizationChecker
from bridge.state import STATE_PENDING_CLOSE, StateStore
from conftest import FakeSnow, make_app_payload


class FakeAkuity:
    """Stands in for AkuityClient; serves whatever payloads the test sets."""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def set_apps(self, *payloads: dict[str, Any]) -> None:
        self.payloads = list(payloads)

    async def list_applications(self) -> list[Application]:
        return [Application.model_validate(p) for p in self.payloads]


def make_settings(window_seconds: float) -> Settings:
    return Settings(
        poll_interval_seconds=1,
        stabilization_window_seconds=window_seconds,
        akuity=AkuitySettings(
            base_url="http://akuity.test", org_id="o", instance_id="i", api_key="k"
        ),
        snow=SnowSettings(base_url="http://snow.test", api_key="k"),
        redis=RedisSettings(),
    )


@pytest.fixture
def akuity() -> FakeAkuity:
    return FakeAkuity()


def make_poller(
    window_seconds: float,
    akuity: FakeAkuity,
    state: StateStore,
    snow: FakeSnow,
    metrics: Metrics,
) -> Poller:
    settings = make_settings(window_seconds)
    lifecycle = CRLifecycle(snow, state, metrics)
    checker = StabilizationChecker(state, lifecycle)
    return Poller(settings, akuity, lifecycle, checker, state, metrics)  # type: ignore[arg-type]


async def test_full_success_lifecycle(
    akuity: FakeAkuity, state: StateStore, snow: FakeSnow, metrics: Metrics
) -> None:
    poller = make_poller(0, akuity, state, snow, metrics)  # window expires immediately

    # Cycle 1: sync starts → CR created and started.
    akuity.set_apps(make_app_payload(phase="Running", health="Progressing"))
    await poller.run_cycle()
    assert len(snow.creates) == 1
    sys_id, create_payload = snow.creates[0]
    assert create_payload["initiated_by"] == "test.user@org.com"

    # Cycle 2: sync succeeded; zero window → closed successful same cycle.
    akuity.set_apps(
        make_app_payload(
            phase="Succeeded",
            finished_at="2026-07-02T14:32:15Z",
            resources=[{"kind": "Deployment", "name": "my-app", "status": "Synced"}],
        )
    )
    await poller.run_cycle()
    assert snow.closes == [(sys_id, "successful", snow.closes[0][2])]
    audit = snow.audits[0][1]
    assert audit["sync_result"] == "Succeeded"
    assert audit["health_check"] == "stabilization_window"
    assert audit["resources_synced"][0]["kind"] == "Deployment"

    # Cycle 3: nothing new — no duplicate CR activity (idempotency).
    await poller.run_cycle()
    assert len(snow.creates) == 1
    assert len(snow.closes) == 1


async def test_stabilization_window_holds_close_until_expiry(
    akuity: FakeAkuity, state: StateStore, snow: FakeSnow, metrics: Metrics
) -> None:
    poller = make_poller(300, akuity, state, snow, metrics)

    akuity.set_apps(make_app_payload(phase="Running"))
    await poller.run_cycle()
    akuity.set_apps(make_app_payload(phase="Succeeded", finished_at="2026-07-02T14:32:15Z"))
    await poller.run_cycle()

    # Still within the window: CR open, pending close.
    assert snow.closes == []
    pending = await state.list_pending()
    assert len(pending) == 1
    assert pending[0].state == STATE_PENDING_CLOSE


async def test_degradation_during_window_closes_unsuccessful(
    akuity: FakeAkuity, state: StateStore, snow: FakeSnow, metrics: Metrics
) -> None:
    poller = make_poller(300, akuity, state, snow, metrics)

    akuity.set_apps(make_app_payload(phase="Running"))
    await poller.run_cycle()
    akuity.set_apps(make_app_payload(phase="Succeeded", finished_at="2026-07-02T14:32:15Z"))
    await poller.run_cycle()

    # App crash-loops within the window.
    akuity.set_apps(
        make_app_payload(phase="Succeeded", finished_at="2026-07-02T14:32:15Z", health="Degraded")
    )
    await poller.run_cycle()

    assert len(snow.closes) == 1
    assert snow.closes[0][1] == "unsuccessful"


async def test_failed_sync_closes_immediately(
    akuity: FakeAkuity, state: StateStore, snow: FakeSnow, metrics: Metrics
) -> None:
    poller = make_poller(300, akuity, state, snow, metrics)

    akuity.set_apps(make_app_payload(phase="Running"))
    await poller.run_cycle()
    akuity.set_apps(
        make_app_payload(
            phase="Failed",
            finished_at="2026-07-02T14:31:45Z",
            health="Degraded",
            message="one or more synchronization tasks are not running",
        )
    )
    await poller.run_cycle()

    assert len(snow.closes) == 1
    _sys_id, result, payload = snow.closes[0]
    assert result == "unsuccessful"
    assert "Sync failed" in payload["close_notes"]
    audit = snow.audits[0][1]
    assert audit["sync_result"] == "Failed"


async def test_fast_sync_backfill_creates_retroactive_cr(
    akuity: FakeAkuity, state: StateStore, snow: FakeSnow, metrics: Metrics
) -> None:
    poller = make_poller(0, akuity, state, snow, metrics)

    # Sync started and completed entirely between polls.
    akuity.set_apps(make_app_payload(phase="Succeeded", finished_at="2026-07-02T14:30:05Z"))
    await poller.run_cycle()

    assert len(snow.creates) == 1
    assert snow.creates[0][1]["discovered_closed"] is True
    # Zero window → closed successful in the same cycle.
    assert len(snow.closes) == 1
    assert snow.closes[0][1] == "successful"


async def test_superseding_sync_closes_prior_cr_on_sync_result(
    akuity: FakeAkuity, state: StateStore, snow: FakeSnow, metrics: Metrics
) -> None:
    poller = make_poller(300, akuity, state, snow, metrics)

    # Sync A runs and succeeds; enters the stabilization window.
    akuity.set_apps(make_app_payload(phase="Running", revision="aaa1111"))
    await poller.run_cycle()
    akuity.set_apps(
        make_app_payload(phase="Succeeded", revision="aaa1111", finished_at="2026-07-02T14:32:15Z")
    )
    await poller.run_cycle()
    cr_a = snow.creates[0][0]

    # Sync B starts before A's window expires.
    akuity.set_apps(
        make_app_payload(phase="Running", revision="bbb2222", started_at="2026-07-02T14:38:00Z")
    )
    await poller.run_cycle()

    # A closed on its stored sync result with the superseded marker; B open.
    assert len(snow.creates) == 2
    assert len(snow.closes) == 1
    assert snow.closes[0][0] == cr_a
    assert snow.closes[0][1] == "successful"
    audit_a = snow.audits[0][1]
    assert audit_a["superseded"] is True
    assert audit_a["health_check"] == "superseded_by_subsequent_sync"
    assert await state.list_pending() == []


async def test_automated_self_heal_is_fully_suppressed(
    akuity: FakeAkuity, state: StateStore, snow: FakeSnow, metrics: Metrics
) -> None:
    poller = make_poller(0, akuity, state, snow, metrics)

    history = [{"revision": "abc1234", "deployedAt": "2026-07-01T10:00:00Z", "id": 41}]

    # Establish last-applied revision via an idle cycle.
    akuity.set_apps(make_app_payload(phase=None, history=history))
    await poller.run_cycle()

    # Controller re-applies the same revision (drift correction).
    akuity.set_apps(
        make_app_payload(
            phase="Running",
            revision="abc1234",
            automated=True,
            username="",
            history=history,
            started_at="2026-07-02T15:00:00Z",
        )
    )
    await poller.run_cycle()

    assert snow.creates == []
    assert snow.closes == []


async def test_snow_create_failure_does_not_block_and_close_is_skipped(
    akuity: FakeAkuity, state: StateStore, snow: FakeSnow, metrics: Metrics
) -> None:
    poller = make_poller(0, akuity, state, snow, metrics)
    snow.fail_creates = True

    akuity.set_apps(make_app_payload(phase="Running"))
    await poller.run_cycle()
    akuity.set_apps(make_app_payload(phase="Succeeded", finished_at="2026-07-02T14:32:15Z"))
    await poller.run_cycle()

    # No CR existed, so no close/audit calls — but the cycle never raised and
    # the operation reached a terminal state.
    assert snow.closes == []
    assert snow.audits == []
    assert await state.list_pending() == []
