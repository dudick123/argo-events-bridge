"""Akuity ArgoCD API client and response models.

The bridge makes ONE list call per poll cycle; the list response carries full
`operationState` for every application. Response shapes are modeled on the
upstream ArgoCD `v1alpha1Application` schema — see docs/akuity-api-examples.md
for annotated examples and open questions on the exact Akuity envelope.
"""

import asyncio
import hashlib

import httpx
from pydantic import BaseModel, ConfigDict, Field

from bridge.config import AkuitySettings
from bridge.logging import get_logger
from bridge.metrics import Metrics

logger = get_logger(__name__)


class InitiatedBy(BaseModel):
    """Identity that initiated a sync operation."""

    model_config = ConfigDict(extra="ignore")

    username: str = ""
    automated: bool = False


class OperationSync(BaseModel):
    """Sync section of an operation: the requested target revision."""

    model_config = ConfigDict(extra="ignore")

    revision: str = ""


class Operation(BaseModel):
    """The operation request that produced an operationState."""

    model_config = ConfigDict(extra="ignore")

    sync: OperationSync | None = None
    initiated_by: InitiatedBy | None = Field(default=None, alias="initiatedBy")


class ResourceResult(BaseModel):
    """Per-resource outcome within a sync result."""

    model_config = ConfigDict(extra="ignore")

    group: str = ""
    version: str = ""
    kind: str = ""
    namespace: str = ""
    name: str = ""
    status: str = ""
    message: str = ""


class SyncResult(BaseModel):
    """Result section of a completed (or failed) sync operation."""

    model_config = ConfigDict(extra="ignore")

    revision: str = ""
    resources: list[ResourceResult] = Field(default_factory=list)


class OperationState(BaseModel):
    """Current (most recent) operation state on an application."""

    model_config = ConfigDict(extra="ignore")

    operation: Operation | None = None
    phase: str = ""
    message: str = ""
    sync_result: SyncResult | None = Field(default=None, alias="syncResult")
    started_at: str = Field(default="", alias="startedAt")
    finished_at: str | None = Field(default=None, alias="finishedAt")

    @property
    def revision(self) -> str:
        """Target revision of this operation, from syncResult or the request."""
        if self.sync_result is not None and self.sync_result.revision:
            return self.sync_result.revision
        if self.operation is not None and self.operation.sync is not None:
            return self.operation.sync.revision
        return ""

    @property
    def initiated_by_username(self) -> str:
        """Username that initiated the sync, or empty string if absent."""
        if self.operation is not None and self.operation.initiated_by is not None:
            return self.operation.initiated_by.username
        return ""

    @property
    def is_automated(self) -> bool:
        """True when the sync was initiated by the controller, not a human."""
        if self.operation is not None and self.operation.initiated_by is not None:
            return self.operation.initiated_by.automated
        return False


class SyncStatus(BaseModel):
    """Application-level sync status."""

    model_config = ConfigDict(extra="ignore")

    status: str = ""
    revision: str = ""


class HealthStatus(BaseModel):
    """Application-level health status."""

    model_config = ConfigDict(extra="ignore")

    status: str = ""
    message: str = ""


class HistoryEntry(BaseModel):
    """One entry in the application deployment history."""

    model_config = ConfigDict(extra="ignore")

    revision: str = ""
    deployed_at: str = Field(default="", alias="deployedAt")
    id: int = 0


class AppStatus(BaseModel):
    """Application status block."""

    model_config = ConfigDict(extra="ignore")

    sync: SyncStatus | None = None
    health: HealthStatus | None = None
    operation_state: OperationState | None = Field(default=None, alias="operationState")
    history: list[HistoryEntry] = Field(default_factory=list)


class AppMetadata(BaseModel):
    """Application metadata: name and labels."""

    model_config = ConfigDict(extra="ignore")

    name: str
    labels: dict[str, str] = Field(default_factory=dict)


class AppDestination(BaseModel):
    """Application destination cluster and namespace."""

    model_config = ConfigDict(extra="ignore")

    server: str = ""
    name: str = ""
    namespace: str = ""


class AppSpec(BaseModel):
    """Application spec subset used by the bridge."""

    model_config = ConfigDict(extra="ignore")

    project: str = ""
    destination: AppDestination | None = None


class Application(BaseModel):
    """ArgoCD Application as returned by the Akuity list endpoint."""

    model_config = ConfigDict(extra="ignore")

    metadata: AppMetadata
    spec: AppSpec | None = None
    status: AppStatus | None = None

    @property
    def operation_state(self) -> OperationState | None:
        """Convenience accessor for status.operationState."""
        return self.status.operation_state if self.status is not None else None

    @property
    def last_applied_revision(self) -> str:
        """Most recently deployed revision from history, or empty string."""
        if self.status is not None and self.status.history:
            newest = max(self.status.history, key=lambda entry: entry.id)
            return newest.revision
        return ""

    @property
    def health_status(self) -> str:
        """Current health status, or empty string if unknown."""
        if self.status is not None and self.status.health is not None:
            return self.status.health.status
        return ""


def operation_key(app_name: str, started_at: str, revision: str) -> str:
    """Compute the natural key identifying one sync operation.

    operationKey = sha256(app.name + operationState.startedAt + revision)
    """
    digest = hashlib.sha256(f"{app_name}{started_at}{revision}".encode()).hexdigest()
    return f"sha256:{digest}"


class AkuityClient:
    """Async client for the Akuity ArgoCD API with 429 backoff."""

    def __init__(
        self,
        settings: AkuitySettings,
        metrics: Metrics,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._metrics = metrics
        self._client = http_client or httpx.AsyncClient(
            base_url=settings.base_url,
            headers={"Authorization": f"Bearer {settings.api_key}"},
            timeout=60.0,
        )

    @property
    def _apps_path(self) -> str:
        s = self._settings
        return f"/api/v1/orgs/{s.org_id}/instances/{s.instance_id}/applications"

    async def list_applications(self) -> list[Application]:
        """List all applications matching the configured label selector.

        One call returns full state (including operationState) for every app.
        Retries with exponential backoff on 429 and 5xx up to max_retries;
        raises the final error if retries are exhausted so the poll cycle can
        skip this tick without corrupting state.
        """
        params = {"selector": self._settings.app_label_selector}
        backoff = 1.0
        last_error: Exception | None = None

        for attempt in range(self._settings.max_retries + 1):
            try:
                response = await self._client.get(self._apps_path, params=params)
                if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                    self._metrics.akuity_rate_limited()
                    retry_after = float(response.headers.get("Retry-After", backoff))
                    logger.warning("akuity_rate_limited", attempt=attempt, retry_after=retry_after)
                    await asyncio.sleep(retry_after)
                    backoff *= 2
                    continue
                response.raise_for_status()
                payload = response.json()
                items = payload.get("items") or []
                return [Application.model_validate(item) for item in items]
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning("akuity_request_failed", attempt=attempt, error=str(exc))
                await asyncio.sleep(backoff)
                backoff *= 2

        raise RuntimeError("Akuity list_applications failed after retries") from last_error

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
