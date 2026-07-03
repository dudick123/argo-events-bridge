"""Pure transition-detection logic.

Given the current application state from the Akuity API and the last-seen
snapshot from Redis, classify what (if anything) happened. This module has no
I/O — it is the unit-testable heart of the bridge. The decision table lives in
docs/akuity-api-examples.md.
"""

from dataclasses import dataclass
from enum import Enum

from bridge.clients.akuity import Application, operation_key
from bridge.state import AppSnapshot

RUNNING = "Running"
SUCCEEDED = "Succeeded"
FAILED_PHASES = frozenset({"Failed", "Error"})
TERMINAL_PHASES = frozenset({SUCCEEDED, *FAILED_PHASES})


class TransitionKind(Enum):
    """Classification of an observed application state change."""

    NONE = "none"
    SYNC_STARTED = "sync_started"
    SYNC_SUCCEEDED = "sync_succeeded"
    SYNC_FAILED = "sync_failed"
    BACKFILL_SUCCEEDED = "backfill_succeeded"
    BACKFILL_FAILED = "backfill_failed"
    SELF_HEAL = "self_heal"


@dataclass
class Transition:
    """A detected transition with its identifying operation key."""

    kind: TransitionKind
    operation_key: str = ""
    phase: str = ""
    revision: str = ""


def detect_transition(app: Application, snapshot: AppSnapshot | None) -> Transition:
    """Classify the change between the last-seen snapshot and current state.

    Rules (docs/akuity-api-examples.md, transition table):

    - No operationState → NONE.
    - New operation (operationKey differs from last seen):
        - automated + same revision as last applied → SELF_HEAL (suppress)
        - phase Running → SYNC_STARTED
        - phase already terminal → BACKFILL_* (completed between polls)
    - Same operation:
        - Running → Succeeded → SYNC_SUCCEEDED (start stabilization)
        - Running → Failed/Error → SYNC_FAILED (close immediately)
        - otherwise → NONE
    """
    op_state = app.operation_state
    if op_state is None or not op_state.started_at:
        return Transition(kind=TransitionKind.NONE)

    revision = op_state.revision
    current_key = operation_key(app.metadata.name, op_state.started_at, revision)
    last_key = snapshot.last_operation_key if snapshot is not None else ""
    last_phase = snapshot.last_phase if snapshot is not None else ""

    if current_key != last_key:
        return _classify_new_operation(app, snapshot, current_key, revision)

    if last_phase == RUNNING and op_state.phase == SUCCEEDED:
        return Transition(
            kind=TransitionKind.SYNC_SUCCEEDED,
            operation_key=current_key,
            phase=op_state.phase,
            revision=revision,
        )
    if last_phase == RUNNING and op_state.phase in FAILED_PHASES:
        return Transition(
            kind=TransitionKind.SYNC_FAILED,
            operation_key=current_key,
            phase=op_state.phase,
            revision=revision,
        )
    return Transition(kind=TransitionKind.NONE, operation_key=current_key)


def _classify_new_operation(
    app: Application, snapshot: AppSnapshot | None, current_key: str, revision: str
) -> Transition:
    """Classify a newly observed operation (operationKey changed)."""
    op_state = app.operation_state
    if op_state is None:  # unreachable: caller guards, kept for type narrowing
        return Transition(kind=TransitionKind.NONE)

    # Self-heal: the controller re-applied the already-deployed revision.
    # A *manual* re-sync of the same revision is a legitimate change and is
    # not suppressed. Auto-sync is disabled on all prod apps, so this branch
    # is a safety net rather than an expected path.
    last_applied = (
        snapshot.last_applied_revision if snapshot is not None else app.last_applied_revision
    )
    if op_state.is_automated and revision and revision == last_applied:
        return Transition(
            kind=TransitionKind.SELF_HEAL,
            operation_key=current_key,
            phase=op_state.phase,
            revision=revision,
        )

    if op_state.phase == RUNNING:
        return Transition(
            kind=TransitionKind.SYNC_STARTED,
            operation_key=current_key,
            phase=op_state.phase,
            revision=revision,
        )

    if op_state.phase == SUCCEEDED:
        return Transition(
            kind=TransitionKind.BACKFILL_SUCCEEDED,
            operation_key=current_key,
            phase=op_state.phase,
            revision=revision,
        )
    if op_state.phase in FAILED_PHASES:
        return Transition(
            kind=TransitionKind.BACKFILL_FAILED,
            operation_key=current_key,
            phase=op_state.phase,
            revision=revision,
        )

    # Unknown or transitional phase (e.g. Terminating) on a new operation:
    # wait for a subsequent poll to classify it.
    return Transition(kind=TransitionKind.NONE, operation_key=current_key)
