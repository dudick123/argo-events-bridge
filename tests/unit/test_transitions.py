"""Unit tests for the transition decision table."""

from bridge.clients.akuity import Application, operation_key
from bridge.state import AppSnapshot
from bridge.transitions import TransitionKind, detect_transition
from conftest import make_app_payload


def app_from(payload: dict) -> Application:  # type: ignore[type-arg]
    return Application.model_validate(payload)


def snapshot_for(
    name: str = "my-app",
    started_at: str = "2026-07-02T14:30:00Z",
    revision: str = "def5678",
    phase: str = "Running",
    last_applied: str = "abc1234",
) -> AppSnapshot:
    return AppSnapshot(
        app_name=name,
        last_operation_key=operation_key(name, started_at, revision),
        last_phase=phase,
        last_applied_revision=last_applied,
    )


def test_idle_app_no_operation_state_is_none() -> None:
    app = app_from(make_app_payload(phase=None))
    assert detect_transition(app, None).kind is TransitionKind.NONE


def test_new_running_operation_is_sync_started() -> None:
    app = app_from(make_app_payload(phase="Running"))
    result = detect_transition(app, None)
    assert result.kind is TransitionKind.SYNC_STARTED
    assert result.revision == "def5678"
    assert result.operation_key == operation_key("my-app", "2026-07-02T14:30:00Z", "def5678")


def test_running_to_succeeded_is_sync_succeeded() -> None:
    app = app_from(make_app_payload(phase="Succeeded"))
    result = detect_transition(app, snapshot_for(phase="Running"))
    assert result.kind is TransitionKind.SYNC_SUCCEEDED


def test_running_to_failed_is_sync_failed() -> None:
    app = app_from(make_app_payload(phase="Failed"))
    result = detect_transition(app, snapshot_for(phase="Running"))
    assert result.kind is TransitionKind.SYNC_FAILED


def test_running_to_error_is_sync_failed() -> None:
    app = app_from(make_app_payload(phase="Error"))
    result = detect_transition(app, snapshot_for(phase="Running"))
    assert result.kind is TransitionKind.SYNC_FAILED


def test_same_operation_same_phase_is_none() -> None:
    app = app_from(make_app_payload(phase="Running"))
    result = detect_transition(app, snapshot_for(phase="Running"))
    assert result.kind is TransitionKind.NONE


def test_completed_operation_never_seen_running_is_backfill_succeeded() -> None:
    app = app_from(make_app_payload(phase="Succeeded"))
    result = detect_transition(app, None)
    assert result.kind is TransitionKind.BACKFILL_SUCCEEDED


def test_failed_operation_never_seen_running_is_backfill_failed() -> None:
    app = app_from(make_app_payload(phase="Failed"))
    result = detect_transition(app, None)
    assert result.kind is TransitionKind.BACKFILL_FAILED


def test_automated_resync_of_applied_revision_is_self_heal() -> None:
    payload = make_app_payload(
        phase="Running",
        revision="abc1234",
        automated=True,
        username="",
        history=[{"revision": "abc1234", "deployedAt": "2026-07-01T10:00:00Z", "id": 41}],
    )
    app = app_from(payload)
    snapshot = snapshot_for(
        started_at="2026-07-01T09:58:00Z",
        revision="abc1234",
        phase="Succeeded",
        last_applied="abc1234",
    )
    result = detect_transition(app, snapshot)
    assert result.kind is TransitionKind.SELF_HEAL


def test_manual_resync_of_applied_revision_is_a_change() -> None:
    payload = make_app_payload(
        phase="Running",
        revision="abc1234",
        automated=False,
        history=[{"revision": "abc1234", "deployedAt": "2026-07-01T10:00:00Z", "id": 41}],
    )
    app = app_from(payload)
    snapshot = snapshot_for(
        started_at="2026-07-01T09:58:00Z",
        revision="abc1234",
        phase="Succeeded",
        last_applied="abc1234",
    )
    result = detect_transition(app, snapshot)
    assert result.kind is TransitionKind.SYNC_STARTED


def test_new_sync_while_previous_pending_is_sync_started() -> None:
    app = app_from(
        make_app_payload(phase="Running", revision="ghi9012", started_at="2026-07-02T14:38:00Z")
    )
    snapshot = snapshot_for(phase="Succeeded")  # prior op, different key
    result = detect_transition(app, snapshot)
    assert result.kind is TransitionKind.SYNC_STARTED
    assert result.revision == "ghi9012"
