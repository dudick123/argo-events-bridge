"""ServiceNow CR API client.

Implements the four lifecycle operations against the assumed contract in
docs/snow-api-contract.md (endpoint paths pending confirmation with the SNOW
team). Failure policy per design: retry with exponential backoff, then log the
full payload and emit a Datadog alert metric — never raise into the poll loop.
"""

import asyncio
from typing import Any, Protocol

import httpx

from bridge.config import SnowSettings
from bridge.logging import get_logger
from bridge.metrics import Metrics

logger = get_logger(__name__)

# Assumed endpoint paths — validate against the live SNOW API before Phase 1
# ships (docs/snow-api-contract.md, open question 1).
CREATE_PATH = "/api/change"
CLOSE_PATH = "/api/change/{sys_id}/close"
AUDIT_PATH = "/api/change/{sys_id}/audit"


class SnowClientProtocol(Protocol):
    """Interface for the SNOW CR lifecycle, for test doubles."""

    async def create_and_start(self, payload: dict[str, Any]) -> str | None:
        """Create and start a CR; return its sys_id, or None on failure."""
        ...

    async def close_successful(self, cr_sys_id: str, payload: dict[str, Any]) -> bool:
        """Close a CR as successful; return True on success."""
        ...

    async def close_unsuccessful(self, cr_sys_id: str, payload: dict[str, Any]) -> bool:
        """Close a CR as unsuccessful; return True on success."""
        ...

    async def attach_audit(self, cr_sys_id: str, audit: dict[str, Any]) -> bool:
        """Attach the audit document to a closed CR; return True on success."""
        ...


class SnowClient:
    """Async SNOW CR API client with retry and log-and-alert failure handling."""

    def __init__(
        self,
        settings: SnowSettings,
        metrics: Metrics,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._metrics = metrics
        self._client = http_client or httpx.AsyncClient(
            base_url=settings.base_url,
            headers={"Authorization": f"Bearer {settings.api_key}"},
            timeout=settings.timeout_seconds,
        )

    async def create_and_start(self, payload: dict[str, Any]) -> str | None:
        """Create and start a CR in one unit of work; return sys_id.

        A 409 (duplicate correlation_id) is treated as success per the
        idempotency contract; the response is expected to carry the existing
        CR's sys_id.
        """
        response = await self._request("create_and_start", "POST", CREATE_PATH, payload)
        if response is None:
            return None
        sys_id = response.get("sys_id")
        return str(sys_id) if sys_id else None

    async def close_successful(self, cr_sys_id: str, payload: dict[str, Any]) -> bool:
        """Close a CR as successful."""
        body = {"result": "successful", **payload}
        path = CLOSE_PATH.format(sys_id=cr_sys_id)
        return await self._request("close_successful", "PATCH", path, body) is not None

    async def close_unsuccessful(self, cr_sys_id: str, payload: dict[str, Any]) -> bool:
        """Close a CR as unsuccessful."""
        body = {"result": "unsuccessful", **payload}
        path = CLOSE_PATH.format(sys_id=cr_sys_id)
        return await self._request("close_unsuccessful", "PATCH", path, body) is not None

    async def attach_audit(self, cr_sys_id: str, audit: dict[str, Any]) -> bool:
        """Attach the audit JSON document to a CR."""
        path = AUDIT_PATH.format(sys_id=cr_sys_id)
        return await self._request("attach_audit", "POST", path, audit) is not None

    async def _request(
        self, method_name: str, http_method: str, path: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Issue one lifecycle call with retries; None means final failure.

        Retry policy: 5xx and transport errors retry with exponential backoff
        up to max_retries. 409 is success (idempotent duplicate). Other 4xx
        are client errors — logged and alerted without retry. On exhaustion,
        the full payload is logged so the CR can be filed manually.
        """
        backoff = self._settings.retry_backoff_base_ms / 1000.0

        for attempt in range(self._settings.max_retries + 1):
            try:
                response = await self._client.request(http_method, path, json=payload)
                if response.status_code == httpx.codes.CONFLICT:
                    logger.info("snow_duplicate_correlation_id", method=method_name)
                    return dict(response.json()) if response.content else {}
                if 400 <= response.status_code < 500:
                    logger.error(
                        "snow_client_error",
                        method=method_name,
                        status=response.status_code,
                        body=response.text,
                        payload=payload,
                    )
                    self._metrics.snow_error(method_name)
                    return None
                response.raise_for_status()
                return dict(response.json()) if response.content else {}
            except httpx.HTTPError as exc:
                logger.warning(
                    "snow_request_failed", method=method_name, attempt=attempt, error=str(exc)
                )
                if attempt < self._settings.max_retries:
                    await asyncio.sleep(backoff)
                    backoff *= 2

        logger.error("snow_retries_exhausted", method=method_name, payload=payload)
        self._metrics.snow_error(method_name)
        return None

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
