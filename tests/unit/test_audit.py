"""Unit tests for audit payload assembly."""

from bridge.audit import (
    HEALTH_CHECK_STABILIZATION,
    HEALTH_CHECK_SUPERSEDED,
    build_audit_document,
    build_close_payload,
    build_create_payload,
)
from bridge.state import OperationRecord


def make_record(**overrides: object) -> OperationRecord:
    defaults: dict[str, object] = {
        "operation_key": "sha256:abc",
        "app_name": "my-app",
        "cr_sys_id": "sys-1",
        "sync_revision": "def5678",
        "started_at": "2026-07-02T14:30:00Z",
        "finished_at": "2026-07-02T14:32:15Z",
        "initiated_by": "test.user@org.com",
        "sync_result": "Succeeded",
        "argo_project": "my-tenant",
        "destination_cluster": "wus3",
        "destination_namespace": "my-namespace",
    }
    defaults.update(overrides)
    return OperationRecord(**defaults)  # type: ignore[arg-type]


def test_create_payload_carries_correlation_id_and_initiator() -> None:
    payload = build_create_payload(make_record())
    assert payload["correlation_id"] == "sha256:abc"
    assert payload["initiated_by"] == "test.user@org.com"
    assert payload["app_name"] == "my-app"
    assert payload["sync_revision"] == "def5678"
    assert "discovered_closed" not in payload


def test_create_payload_flags_discovered_closed_backfills() -> None:
    payload = build_create_payload(make_record(discovered_closed=True))
    assert payload["discovered_closed"] is True


def test_close_payload_contains_notes_and_finished_at() -> None:
    payload = build_close_payload(make_record(), "All good.")
    assert payload["close_notes"] == "All good."
    assert payload["finished_at"] == "2026-07-02T14:32:15Z"


def test_audit_document_stabilization_success() -> None:
    audit = build_audit_document(make_record(), "Healthy", HEALTH_CHECK_STABILIZATION)
    assert audit["health_outcome"] == "Healthy"
    assert audit["health_check"] == HEALTH_CHECK_STABILIZATION
    assert audit["sync_result"] == "Succeeded"
    assert audit["initiated_by"] == "test.user@org.com"
    assert audit["superseded"] is False


def test_audit_document_superseded_flag() -> None:
    audit = build_audit_document(make_record(superseded=True), "", HEALTH_CHECK_SUPERSEDED)
    assert audit["superseded"] is True
    assert audit["health_check"] == HEALTH_CHECK_SUPERSEDED
