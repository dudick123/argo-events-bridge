"""Unit tests for the stabilization window checker."""

import time

import pytest

from bridge.lifecycle import CRLifecycle
from bridge.metrics import Metrics
from bridge.stabilization import StabilizationChecker
from bridge.state import STATE_CLOSED, STATE_PENDING_CLOSE, OperationRecord, StateStore
from conftest import FakeSnow


def pending_record(deadline_offset: float) -> OperationRecord:
    return OperationRecord(
        operation_key="sha256:abc",
        app_name="my-app",
        cr_sys_id="sys-1",
        state=STATE_PENDING_CLOSE,
        close_deadline=time.time() + deadline_offset,
        sync_result="Succeeded",
        finished_at="2026-07-02T14:32:15Z",
    )


@pytest.fixture
def checker(state: StateStore, snow: FakeSnow, metrics: Metrics) -> StabilizationChecker:
    return StabilizationChecker(state, CRLifecycle(snow, state, metrics))


async def test_healthy_through_expired_window_closes_successful(
    state: StateStore, snow: FakeSnow, checker: StabilizationChecker
) -> None:
    await state.save_operation(pending_record(deadline_offset=-1))
    await checker.check({"my-app": "Healthy"})

    assert snow.closes == [
        (
            "sys-1",
            "successful",
            {
                "finished_at": "2026-07-02T14:32:15Z",
                "close_notes": (
                    "Sync succeeded. App remained Healthy through the stabilization window."
                ),
            },
        )
    ]
    assert len(snow.audits) == 1
    record = await state.get_operation("sha256:abc")
    assert record is not None
    assert record.state == STATE_CLOSED
    assert await state.list_pending() == []


async def test_degraded_within_window_closes_unsuccessful_immediately(
    state: StateStore, snow: FakeSnow, checker: StabilizationChecker
) -> None:
    await state.save_operation(pending_record(deadline_offset=300))
    await checker.check({"my-app": "Degraded"})

    assert len(snow.closes) == 1
    assert snow.closes[0][1] == "unsuccessful"
    audit = snow.audits[0][1]
    assert audit["health_outcome"] == "Degraded"


async def test_healthy_within_window_stays_pending(
    state: StateStore, snow: FakeSnow, checker: StabilizationChecker
) -> None:
    await state.save_operation(pending_record(deadline_offset=300))
    await checker.check({"my-app": "Healthy"})

    assert snow.closes == []
    assert len(await state.list_pending()) == 1


async def test_progressing_health_does_not_fail_the_window(
    state: StateStore, snow: FakeSnow, checker: StabilizationChecker
) -> None:
    await state.save_operation(pending_record(deadline_offset=300))
    await checker.check({"my-app": "Progressing"})

    assert snow.closes == []
    assert len(await state.list_pending()) == 1
