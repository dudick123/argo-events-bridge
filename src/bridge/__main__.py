"""Bridge entrypoint: wires components and runs the event loop.

Runs three concurrent tasks on a single asyncio loop:
- the poller (which also drives stabilization checks each cycle),
- the FastAPI health server,
and shuts down cleanly on SIGTERM/SIGINT.
"""

import asyncio
import signal

import redis.asyncio as aioredis
import uvicorn

from bridge.clients.akuity import AkuityClient
from bridge.clients.snow import SnowClient
from bridge.config import load_settings
from bridge.health import create_app
from bridge.lifecycle import CRLifecycle
from bridge.logging import configure_logging, get_logger
from bridge.metrics import Metrics
from bridge.poller import Poller
from bridge.stabilization import StabilizationChecker
from bridge.state import StateStore


async def main() -> None:
    """Configure, wire, and run the bridge until signalled to stop."""
    settings = load_settings()
    obs = settings.observability
    configure_logging(obs.log_level, obs.service_name, obs.env)
    logger = get_logger(__name__)

    metrics = Metrics(
        host=obs.datadog_statsd_host,
        port=obs.datadog_statsd_port,
        service_name=obs.service_name,
        env=obs.env,
    )

    redis_client = aioredis.from_url(settings.redis.url, decode_responses=True)
    state = StateStore(redis_client, settings.redis.key_ttl_seconds)

    akuity = AkuityClient(settings.akuity, metrics)
    snow = SnowClient(settings.snow, metrics)
    lifecycle = CRLifecycle(snow, state, metrics)
    stabilization = StabilizationChecker(state, lifecycle)
    poller = Poller(settings, akuity, lifecycle, stabilization, state, metrics)

    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="0.0.0.0", port=8000, log_config=None)  # noqa: S104
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, poller.stop)
        loop.add_signal_handler(sig, lambda: setattr(server, "should_exit", True))

    logger.info(
        "bridge_starting",
        poll_interval_seconds=settings.poll_interval_seconds,
        stabilization_window_seconds=settings.stabilization_window_seconds,
        label_selector=settings.akuity.app_label_selector,
    )

    try:
        await asyncio.gather(poller.run_forever(), server.serve())
    finally:
        await akuity.aclose()
        await snow.aclose()
        await redis_client.aclose()
        logger.info("bridge_stopped")


if __name__ == "__main__":
    asyncio.run(main())
