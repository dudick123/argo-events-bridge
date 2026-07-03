"""DogStatsD metric emission.

Metric names follow the scheme documented in docs/EVENT-BRIDGE-DESIGN.md §9.
The DogStatsD client is fire-and-forget UDP; emission never raises into the
polling loop.
"""

from datadog.dogstatsd.base import DogStatsd


class Metrics:
    """Thin wrapper over DogStatsD with the bridge's metric vocabulary."""

    def __init__(self, host: str, port: int, service_name: str, env: str) -> None:
        self._statsd = DogStatsd(
            host=host,
            port=port,
            constant_tags=[f"service:{service_name}", f"env:{env}"],
        )

    def poll_duration(self, seconds: float) -> None:
        """Record the wall time of one full poll cycle."""
        self._statsd.histogram("bridge.poll.duration", seconds)

    def apps_polled(self, count: int) -> None:
        """Record the number of applications processed in one cycle."""
        self._statsd.gauge("bridge.apps.polled", count)

    def transition_detected(self, kind: str) -> None:
        """Count a detected transition, tagged by kind.

        Kinds: running, succeeded, failed, backfill, superseded, self_heal.
        """
        self._statsd.increment("bridge.transitions.detected", tags=[f"kind:{kind}"])

    def cr_created(self) -> None:
        """Count a CR successfully created and started in SNOW."""
        self._statsd.increment("bridge.cr.created")

    def cr_closed(self, result: str) -> None:
        """Count a CR closed, tagged by result: successful | unsuccessful | superseded."""
        self._statsd.increment("bridge.cr.closed", tags=[f"result:{result}"])

    def snow_error(self, method: str) -> None:
        """Count a SNOW API failure after retry exhaustion, tagged by client method."""
        self._statsd.increment("bridge.snow.errors", tags=[f"method:{method}"])

    def akuity_rate_limited(self) -> None:
        """Count a 429 response from the Akuity API."""
        self._statsd.increment("bridge.akuity.429s")
