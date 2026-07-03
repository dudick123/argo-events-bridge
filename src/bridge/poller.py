"""Main polling loop: list applications, detect transitions, drive CR actions.

One Akuity list call per cycle covers all prod applications. Per-app
processing is sequential and synchronous within the cycle — at 500 apps the
in-memory diff is negligible next to the single HTTP call. The stabilization
checker runs at the end of each cycle using the same response's health data.
"""

import asyncio
import time

from bridge.audit import HEALTH_CHECK_NONE, HEALTH_CHECK_SUPERSEDED
from bridge.clients.akuity import AkuityClient, Application
from bridge.config import Settings
from bridge.lifecycle import CRLifecycle
from bridge.logging import get_logger
from bridge.metrics import Metrics
from bridge.stabilization import StabilizationChecker
from bridge.state import (
    STATE_OPEN,
    STATE_PENDING_CLOSE,
    AppSnapshot,
    OperationRecord,
    StateStore,
)
from bridge.transitions import SUCCEEDED, Transition, TransitionKind, detect_transition

logger = get_logger(__name__)


class Poller:
    """Orchestrates poll cycles; contains no transition or CR business logic."""

    def __init__(
        self,
        settings: Settings,
        akuity: AkuityClient,
        lifecycle: CRLifecycle,
        stabilization: StabilizationChecker,
        state: StateStore,
        metrics: Metrics,
    ) -> None:
        self._settings = settings
        self._akuity = akuity
        self._lifecycle = lifecycle
        self._stabilization = stabilization
        self._state = state
        self._metrics = metrics
        self._running = False

    async def run_forever(self) -> None:
        """Run poll cycles until stop() is called.

        A failed cycle (e.g. Akuity unreachable after retries) is logged and
        skipped; state in Redis is only mutated on observed transitions, so a
        missed cycle degrades to detection latency, never corruption.
        """
        self._running = True
        while self._running:
            started = time.monotonic()
            try:
                await self.run_cycle()
            except Exception:
                logger.exception("poll_cycle_failed")
            elapsed = time.monotonic() - started
            self._metrics.poll_duration(elapsed)
            delay = max(self._settings.poll_interval_seconds - elapsed, 0)
            await asyncio.sleep(delay)

    def stop(self) -> None:
        """Signal run_forever to exit after the current cycle."""
        self._running = False

    async def run_cycle(self) -> None:
        """Execute one poll cycle: list, diff, act, check stabilization."""
        apps = await self._akuity.list_applications()
        self._metrics.apps_polled(len(apps))

        for app in apps:
            try:
                await self._process_app(app)
            except Exception:
                logger.exception("app_processing_failed", app_name=app.metadata.name)

        app_health = {app.metadata.name: app.health_status for app in apps}
        await self._stabilization.check(app_health)

    async def _process_app(self, app: Application) -> None:
        """Detect and dispatch the transition for one application."""
        name = app.metadata.name
        snapshot = await self._state.get_app_snapshot(name)
        transition = detect_transition(app, snapshot)

        if transition.kind is TransitionKind.NONE:
            await self._maybe_update_snapshot(app, snapshot, transition)
            return

        self._metrics.transition_detected(transition.kind.value)
        logger.info(
            "transition_detected",
            app_name=name,
            kind=transition.kind.value,
            operation_key=transition.operation_key,
            revision=transition.revision,
        )

        if transition.kind is TransitionKind.SELF_HEAL:
            # Suppressed entirely: not a change. Snapshot advances so the
            # same operation is not reclassified every cycle.
            await self._save_snapshot(app, transition)
            return

        if transition.kind is TransitionKind.SYNC_STARTED:
            await self._supersede_pending(name, transition.operation_key)
            record = self._build_record(app, transition)
            await self._lifecycle.open_cr(record)

        elif transition.kind is TransitionKind.SYNC_SUCCEEDED:
            await self._enter_stabilization(app, transition)

        elif transition.kind is TransitionKind.SYNC_FAILED:
            await self._close_failed(app, transition)

        elif transition.kind is TransitionKind.BACKFILL_SUCCEEDED:
            await self._supersede_pending(name, transition.operation_key)
            record = self._build_record(app, transition, discovered_closed=True)
            record = await self._lifecycle.open_cr(record)
            await self._start_window(record, app)

        elif transition.kind is TransitionKind.BACKFILL_FAILED:
            await self._supersede_pending(name, transition.operation_key)
            record = self._build_record(app, transition, discovered_closed=True)
            record = await self._lifecycle.open_cr(record)
            await self._close_record_failed(record, app)

        await self._save_snapshot(app, transition)

    # -- Transition handlers -------------------------------------------------

    async def _enter_stabilization(self, app: Application, transition: Transition) -> None:
        """Sync succeeded: capture the result and start the health window."""
        record = await self._state.get_operation(transition.operation_key)
        if record is None:
            # Create was missed (e.g. state loss); rebuild from current data.
            record = self._build_record(app, transition, discovered_closed=True)
            record = await self._lifecycle.open_cr(record)
        await self._start_window(record, app)

    async def _start_window(self, record: OperationRecord, app: Application) -> None:
        """Move a record into pending_close with a stabilization deadline."""
        op_state = app.operation_state
        record.sync_result = SUCCEEDED
        record.finished_at = op_state.finished_at if op_state is not None else None
        if op_state is not None and op_state.sync_result is not None:
            record.resources = [r.model_dump() for r in op_state.sync_result.resources]
        record.state = STATE_PENDING_CLOSE
        record.close_deadline = time.time() + self._settings.stabilization_window_seconds
        await self._state.save_operation(record)

    async def _close_failed(self, app: Application, transition: Transition) -> None:
        """Sync failed: close the CR unsuccessfully right away."""
        record = await self._state.get_operation(transition.operation_key)
        if record is None:
            record = self._build_record(app, transition, discovered_closed=True)
            record = await self._lifecycle.open_cr(record)
        await self._close_record_failed(record, app)

    async def _close_record_failed(self, record: OperationRecord, app: Application) -> None:
        """Close a record as unsuccessful with current sync failure details."""
        op_state = app.operation_state
        record.sync_result = op_state.phase if op_state is not None else "Failed"
        record.finished_at = op_state.finished_at if op_state is not None else None
        if op_state is not None and op_state.sync_result is not None:
            record.resources = [r.model_dump() for r in op_state.sync_result.resources]
        message = op_state.message if op_state is not None else ""
        await self._lifecycle.close_cr(
            record,
            successful=False,
            health_outcome=app.health_status,
            health_check=HEALTH_CHECK_NONE,
            close_notes=f"Sync failed. Phase: {record.sync_result}. Message: {message}",
        )

    async def _supersede_pending(self, app_name: str, new_operation_key: str) -> None:
        """Close any pending-close CR for this app before opening a new one.

        Per design: concurrent CRs are independent, and once a new sync
        starts, the prior operation's state is unobservable — so the pending
        CR closes on its stored sync result, flagged superseded.
        """
        pending = await self._state.find_pending_for_app(app_name)
        if pending is None or pending.operation_key == new_operation_key:
            return
        pending.superseded = True
        self._metrics.transition_detected("superseded")
        await self._lifecycle.close_cr(
            pending,
            successful=pending.sync_result == SUCCEEDED,
            health_outcome="",
            health_check=HEALTH_CHECK_SUPERSEDED,
            close_notes=(
                "Closed on sync result; a subsequent sync started before the "
                "stabilization window completed."
            ),
        )

    # -- Helpers --------------------------------------------------------------

    def _build_record(
        self, app: Application, transition: Transition, discovered_closed: bool = False
    ) -> OperationRecord:
        """Build a new operation record from the current application state."""
        op_state = app.operation_state
        destination = app.spec.destination if app.spec is not None else None
        return OperationRecord(
            operation_key=transition.operation_key,
            app_name=app.metadata.name,
            state=STATE_OPEN,
            sync_revision=transition.revision,
            started_at=op_state.started_at if op_state is not None else "",
            initiated_by=op_state.initiated_by_username if op_state is not None else "",
            discovered_closed=discovered_closed,
            argo_project=app.spec.project if app.spec is not None else "",
            destination_cluster=(destination.name or destination.server) if destination else "",
            destination_namespace=destination.namespace if destination else "",
        )

    async def _save_snapshot(self, app: Application, transition: Transition) -> None:
        """Persist the last-seen snapshot after handling a transition."""
        op_state = app.operation_state
        await self._state.save_app_snapshot(
            AppSnapshot(
                app_name=app.metadata.name,
                last_operation_key=transition.operation_key,
                last_phase=op_state.phase if op_state is not None else "",
                last_applied_revision=app.last_applied_revision,
            )
        )

    async def _maybe_update_snapshot(
        self, app: Application, snapshot: AppSnapshot | None, transition: Transition
    ) -> None:
        """Keep the snapshot's applied-revision current on quiet cycles.

        Written only when something changed, to avoid 500 Redis writes per
        idle cycle.
        """
        if snapshot is None:
            await self._save_snapshot(app, transition)
            return
        op_state = app.operation_state
        current_phase = op_state.phase if op_state is not None else ""
        if (
            snapshot.last_applied_revision != app.last_applied_revision
            or snapshot.last_phase != current_phase
            or snapshot.last_operation_key != transition.operation_key
        ):
            await self._save_snapshot(app, transition)
