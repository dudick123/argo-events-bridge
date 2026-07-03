"""Redis-backed bridge state.

Two record types, both stored as JSON strings:

- ``opkey:{operationKey}`` — one record per sync operation, holding the CR
  sys_id, lifecycle state, stabilization deadline, and audit-relevant fields.
- ``app:{name}`` — last-seen snapshot per application, used by transition
  detection to diff against the current poll.

Operations awaiting stabilization are additionally indexed in the
``pending_close`` set so the deadline checker can enumerate them without
scanning all keys. State must survive pod restarts — never cache these
records in process memory across cycles.
"""

import json
from dataclasses import asdict, dataclass, field
from typing import Any

import redis.asyncio as aioredis

OPKEY_PREFIX = "opkey:"
APP_PREFIX = "app:"
PENDING_SET = "pending_close"

# Operation lifecycle states.
STATE_OPEN = "open"
STATE_PENDING_CLOSE = "pending_close"
STATE_CLOSED = "closed"


@dataclass
class OperationRecord:
    """Durable record of one sync operation and its CR lifecycle."""

    operation_key: str
    app_name: str
    cr_sys_id: str | None = None
    state: str = STATE_OPEN
    close_deadline: float | None = None
    sync_result: str = ""
    sync_revision: str = ""
    started_at: str = ""
    finished_at: str | None = None
    initiated_by: str = ""
    superseded: bool = False
    discovered_closed: bool = False
    argo_project: str = ""
    destination_cluster: str = ""
    destination_namespace: str = ""
    resources: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AppSnapshot:
    """Last-seen application state used for transition detection."""

    app_name: str
    last_operation_key: str = ""
    last_phase: str = ""
    last_applied_revision: str = ""


class StateStore:
    """Async Redis wrapper for bridge state records."""

    def __init__(self, redis_client: aioredis.Redis, key_ttl_seconds: int) -> None:
        self._redis = redis_client
        self._ttl = key_ttl_seconds

    # -- Operation records -------------------------------------------------

    async def get_operation(self, operation_key: str) -> OperationRecord | None:
        """Fetch an operation record, or None if unknown/expired."""
        raw = await self._redis.get(f"{OPKEY_PREFIX}{operation_key}")
        if raw is None:
            return None
        return OperationRecord(**json.loads(raw))

    async def save_operation(self, record: OperationRecord) -> None:
        """Persist an operation record and maintain the pending index."""
        key = f"{OPKEY_PREFIX}{record.operation_key}"
        await self._redis.set(key, json.dumps(asdict(record)), ex=self._ttl)
        if record.state == STATE_PENDING_CLOSE:
            await self._redis.sadd(PENDING_SET, record.operation_key)
        else:
            await self._redis.srem(PENDING_SET, record.operation_key)

    async def list_pending(self) -> list[OperationRecord]:
        """Return all operations awaiting stabilization close.

        Members whose record has expired are pruned from the index.
        """
        members: set[bytes | str] = await self._redis.smembers(PENDING_SET)
        keys = {m.decode() if isinstance(m, bytes) else m for m in members}
        records: list[OperationRecord] = []
        for op_key in keys:
            record = await self.get_operation(op_key)
            if record is None:
                await self._redis.srem(PENDING_SET, op_key)
            else:
                records.append(record)
        return records

    async def find_pending_for_app(self, app_name: str) -> OperationRecord | None:
        """Return the pending-close operation for an app, if any."""
        for record in await self.list_pending():
            if record.app_name == app_name:
                return record
        return None

    # -- App snapshots ------------------------------------------------------

    async def get_app_snapshot(self, app_name: str) -> AppSnapshot | None:
        """Fetch the last-seen snapshot for an app, or None on first sight."""
        raw = await self._redis.get(f"{APP_PREFIX}{app_name}")
        if raw is None:
            return None
        return AppSnapshot(**json.loads(raw))

    async def save_app_snapshot(self, snapshot: AppSnapshot) -> None:
        """Persist the last-seen snapshot for an app (no TTL — always live)."""
        key = f"{APP_PREFIX}{snapshot.app_name}"
        await self._redis.set(key, json.dumps(asdict(snapshot)))
