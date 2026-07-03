"""Audit payload assembly.

Phase 1: the audit document is sourced entirely from ArgoCD data captured on
the operation record — no ADO calls. Schema per docs/EVENT-BRIDGE-DESIGN.md §7.
"""

from datetime import UTC, datetime
from typing import Any

from bridge.state import OperationRecord

HEALTH_CHECK_STABILIZATION = "stabilization_window"
HEALTH_CHECK_SUPERSEDED = "superseded_by_subsequent_sync"
HEALTH_CHECK_NONE = "none"


def build_create_payload(record: OperationRecord) -> dict[str, Any]:
    """Build the create-and-start request body for a new CR."""
    payload: dict[str, Any] = {
        "correlation_id": record.operation_key,
        "app_name": record.app_name,
        "initiated_by": record.initiated_by,
        "sync_revision": record.sync_revision,
        "started_at": record.started_at,
        "argo_project": record.argo_project,
        "destination_cluster": record.destination_cluster,
        "destination_namespace": record.destination_namespace,
        "description": (
            f"ArgoCD sync initiated by {record.initiated_by or 'unknown'} "
            f"for app {record.app_name} revision {record.sync_revision}"
        ),
    }
    if record.discovered_closed:
        payload["discovered_closed"] = True
    return payload


def build_close_payload(record: OperationRecord, close_notes: str) -> dict[str, Any]:
    """Build the close request body (result field is added by the client)."""
    return {
        "finished_at": record.finished_at,
        "close_notes": close_notes,
    }


def build_audit_document(
    record: OperationRecord,
    health_outcome: str,
    health_check: str,
) -> dict[str, Any]:
    """Assemble the Phase 1 audit JSON attached to the CR after close.

    Args:
        record: The completed operation record.
        health_outcome: Final observed health status (e.g. "Healthy").
        health_check: How success was determined — one of the
            HEALTH_CHECK_* constants.
    """
    return {
        "operation_key": record.operation_key,
        "app_name": record.app_name,
        "initiated_by": record.initiated_by,
        "sync_revision": record.sync_revision,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "stabilized_at": datetime.now(tz=UTC).isoformat(),
        "sync_result": record.sync_result,
        "health_outcome": health_outcome,
        "health_check": health_check,
        "superseded": record.superseded,
        "discovered_closed": record.discovered_closed,
        "argo_project": record.argo_project,
        "destination_cluster": record.destination_cluster,
        "destination_namespace": record.destination_namespace,
        "resources_synced": record.resources,
    }
