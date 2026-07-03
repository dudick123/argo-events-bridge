"""Unit tests for the Redis state store."""


from bridge.state import (
    STATE_CLOSED,
    STATE_PENDING_CLOSE,
    AppSnapshot,
    OperationRecord,
    StateStore,
)


async def test_operation_roundtrip(state: StateStore) -> None:
    record = OperationRecord(
        operation_key="sha256:abc",
        app_name="my-app",
        cr_sys_id="sys-1",
        sync_revision="def5678",
        initiated_by="test.user@org.com",
        resources=[{"kind": "Deployment", "name": "my-app"}],
    )
    await state.save_operation(record)
    loaded = await state.get_operation("sha256:abc")
    assert loaded == record


async def test_unknown_operation_returns_none(state: StateStore) -> None:
    assert await state.get_operation("sha256:missing") is None


async def test_pending_index_tracks_pending_close_state(state: StateStore) -> None:
    record = OperationRecord(
        operation_key="sha256:abc", app_name="my-app", state=STATE_PENDING_CLOSE
    )
    await state.save_operation(record)
    pending = await state.list_pending()
    assert [r.operation_key for r in pending] == ["sha256:abc"]

    record.state = STATE_CLOSED
    await state.save_operation(record)
    assert await state.list_pending() == []


async def test_find_pending_for_app(state: StateStore) -> None:
    await state.save_operation(
        OperationRecord(operation_key="sha256:a", app_name="app-a", state=STATE_PENDING_CLOSE)
    )
    await state.save_operation(
        OperationRecord(operation_key="sha256:b", app_name="app-b", state=STATE_PENDING_CLOSE)
    )
    found = await state.find_pending_for_app("app-b")
    assert found is not None
    assert found.operation_key == "sha256:b"
    assert await state.find_pending_for_app("app-c") is None


async def test_app_snapshot_roundtrip(state: StateStore) -> None:
    snapshot = AppSnapshot(
        app_name="my-app",
        last_operation_key="sha256:abc",
        last_phase="Running",
        last_applied_revision="abc1234",
    )
    await state.save_app_snapshot(snapshot)
    loaded = await state.get_app_snapshot("my-app")
    assert loaded == snapshot
    assert await state.get_app_snapshot("other-app") is None
