"""Health endpoint for Kubernetes probes.

The bridge exposes only /healthz — it receives no webhooks and serves no
other traffic.
"""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Build the FastAPI app serving the health endpoint."""
    app = FastAPI(title="change-bridge", docs_url=None, redoc_url=None)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
