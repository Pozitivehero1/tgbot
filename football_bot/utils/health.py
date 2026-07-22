"""Health checker — validates that all external dependencies are reachable."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Awaitable

from football_bot.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HealthResult:
    name: str
    healthy: bool
    latency_ms: float = 0.0
    error: str = ""
    checked_at: datetime = field(default_factory=datetime.utcnow)


class HealthChecker:
    """Aggregates health checks for all critical services."""

    def __init__(self) -> None:
        self._checks: dict[str, Callable[[], Awaitable[bool]]] = {}

    def register(self, name: str, check_fn: Callable[[], Awaitable[bool]]) -> None:
        self._checks[name] = check_fn

    async def run_all(self) -> list[HealthResult]:
        import time

        results: list[HealthResult] = []
        for name, check_fn in self._checks.items():
            start = time.monotonic()
            try:
                healthy = await check_fn()
                latency_ms = (time.monotonic() - start) * 1000
                results.append(HealthResult(name=name, healthy=healthy, latency_ms=latency_ms))
            except Exception as exc:
                latency_ms = (time.monotonic() - start) * 1000
                results.append(
                    HealthResult(
                        name=name,
                        healthy=False,
                        latency_ms=latency_ms,
                        error=str(exc),
                    )
                )
            logger.info(
                "health_check",
                service=name,
                healthy=results[-1].healthy,
                latency_ms=round(results[-1].latency_ms, 1),
                error=results[-1].error or None,
            )
        return results

    def all_healthy(self, results: list[HealthResult]) -> bool:
        return all(r.healthy for r in results)

    def critical_healthy(self, results: list[HealthResult], critical: list[str]) -> bool:
        critical_set = set(critical)
        for r in results:
            if r.name in critical_set and not r.healthy:
                return False
        return True
