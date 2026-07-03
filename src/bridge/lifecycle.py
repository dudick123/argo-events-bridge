"""CR lifecycle actions: open and close operations against SNOW.

Shared by the poller (immediate opens/closes, supersede handling) and the
stabilization checker (window-expiry closes). Every action persists the
operation record so a bridge restart never repeats or drops a lifecycle call.
"""

from bridge.audit import build_audit_document, build_close_payload, build_create_payload
from bridge.clients.snow import SnowClientProtocol
from bridge.logging import get_logger
from bridge.metrics import Metrics
from bridge.state import STATE_CLOSED, OperationRecord, StateStore

logger = get_logger(__name__)


class CRLifecycle:
    """Executes CR lifecycle actions and persists the resulting state."""

    def __init__(self, snow: SnowClientProtocol, state: StateStore, metrics: Metrics) -> None:
        self._snow = snow
        self._state = state
        self._metrics = metrics

    async def open_cr(self, record: OperationRecord) -> OperationRecord:
        """Create and start a CR for a newly detected sync operation.

        On SNOW failure the record is still persisted (cr_sys_id=None) so the
        operation is tracked and later close attempts are logged rather than
        silently lost.
        """
        payload = build_create_payload(record)
        record.cr_sys_id = await self._snow.create_and_start(payload)
        if record.cr_sys_id is not None:
            self._metrics.cr_created()
            logger.info(
                "cr_created",
                operation_key=record.operation_key,
                app_name=record.app_name,
                cr_sys_id=record.cr_sys_id,
                initiated_by=record.initiated_by,
            )
        await self._state.save_operation(record)
        return record

    async def close_cr(
        self,
        record: OperationRecord,
        successful: bool,
        health_outcome: str,
        health_check: str,
        close_notes: str,
    ) -> OperationRecord:
        """Close a CR, attach the audit document, and persist the record.

        Args:
            record: The operation to close.
            successful: Close result reported to SNOW.
            health_outcome: Final observed health for the audit document.
            health_check: HEALTH_CHECK_* constant describing how the outcome
                was determined.
            close_notes: Human-readable close notes for the CR.
        """
        result_tag = "successful" if successful else "unsuccessful"
        if record.superseded:
            result_tag = "superseded"

        if record.cr_sys_id is None:
            logger.error(
                "cr_close_skipped_no_sys_id",
                operation_key=record.operation_key,
                app_name=record.app_name,
                result=result_tag,
            )
        else:
            close_payload = build_close_payload(record, close_notes)
            if successful:
                await self._snow.close_successful(record.cr_sys_id, close_payload)
            else:
                await self._snow.close_unsuccessful(record.cr_sys_id, close_payload)

            audit = build_audit_document(record, health_outcome, health_check)
            await self._snow.attach_audit(record.cr_sys_id, audit)

            self._metrics.cr_closed(result_tag)
            logger.info(
                "cr_closed",
                operation_key=record.operation_key,
                app_name=record.app_name,
                cr_sys_id=record.cr_sys_id,
                result=result_tag,
                health_outcome=health_outcome,
                health_check=health_check,
            )

        record.state = STATE_CLOSED
        await self._state.save_operation(record)
        return record
