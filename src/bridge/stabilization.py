"""Stabilization window checks for pending-close operations.

After a sync succeeds, the CR stays open for a configurable window (default
5 minutes) to confirm the app remains Healthy. The checker runs once per poll
cycle against the health observed in that cycle's list response:

- Degraded within the window → close unsuccessful immediately.
- Deadline expired while Healthy → close successful.

Deadlines live in Redis, so a bridge restart resumes pending windows intact.
"""

import time

from bridge.audit import HEALTH_CHECK_STABILIZATION
from bridge.lifecycle import CRLifecycle
from bridge.logging import get_logger
from bridge.state import StateStore

logger = get_logger(__name__)

DEGRADED = "Degraded"
HEALTHY = "Healthy"


class StabilizationChecker:
    """Evaluates pending-close operations against health and deadlines."""

    def __init__(self, state: StateStore, lifecycle: CRLifecycle) -> None:
        self._state = state
        self._lifecycle = lifecycle

    async def check(self, app_health: dict[str, str]) -> None:
        """Process all pending-close operations for this poll cycle.

        Args:
            app_health: Current health status per app name, taken from this
                cycle's Akuity list response. Apps absent from the map (e.g.
                deleted mid-window) are closed on deadline expiry using the
                last known sync result.
        """
        now = time.time()
        for record in await self._state.list_pending():
            health = app_health.get(record.app_name, "")

            if health == DEGRADED:
                logger.info(
                    "stabilization_degraded",
                    operation_key=record.operation_key,
                    app_name=record.app_name,
                )
                await self._lifecycle.close_cr(
                    record,
                    successful=False,
                    health_outcome=health,
                    health_check=HEALTH_CHECK_STABILIZATION,
                    close_notes=(
                        "Sync succeeded but app health degraded within the stabilization window."
                    ),
                )
                continue

            if record.close_deadline is not None and now >= record.close_deadline:
                await self._lifecycle.close_cr(
                    record,
                    successful=True,
                    health_outcome=health or HEALTHY,
                    health_check=HEALTH_CHECK_STABILIZATION,
                    close_notes=(
                        "Sync succeeded. App remained Healthy through the stabilization window."
                    ),
                )
