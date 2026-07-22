"""PerformanceAnalyzer — measures and tracks bot run performance."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator

from football_bot.utils.logger import get_logger
from football_bot.utils.metrics import MetricsCollector

logger = get_logger(__name__)


@dataclass
class OperationResult:
    name: str
    success: bool
    duration_seconds: float
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.utcnow)


class PerformanceAnalyzer:
    """Tracks performance of individual operations within a run."""

    def __init__(self, metrics: MetricsCollector) -> None:
        self._metrics = metrics
        self._results: list[OperationResult] = []

    @asynccontextmanager
    async def track(self, operation_name: str) -> AsyncGenerator[None, None]:
        """Context manager that records duration and success/failure of an operation."""
        start = time.monotonic()
        error = ""
        success = True
        try:
            yield
        except Exception as exc:
            success = False
            error = str(exc)
            raise
        finally:
            duration = time.monotonic() - start
            result = OperationResult(
                name=operation_name,
                success=success,
                duration_seconds=round(duration, 3),
                error=error,
            )
            self._results.append(result)
            self._metrics.record_timing(operation_name, duration)
            if not success:
                self._metrics.increment(f"error_{operation_name}")
            logger.info(
                "operation_complete",
                operation=operation_name,
                success=success,
                duration=round(duration, 3),
                error=error or None,
            )

    def summary(self) -> dict[str, Any]:
        total = len(self._results)
        succeeded = sum(1 for r in self._results if r.success)
        failed = total - succeeded
        total_duration = sum(r.duration_seconds for r in self._results)
        return {
            "total_operations": total,
            "succeeded": succeeded,
            "failed": failed,
            "total_duration_seconds": round(total_duration, 3),
            "operations": [
                {
                    "name": r.name,
                    "success": r.success,
                    "duration": r.duration_seconds,
                    "error": r.error or None,
                }
                for r in self._results
            ],
        }

    def has_failures(self) -> bool:
        return any(not r.success for r in self._results)

    def slowest_operation(self) -> OperationResult | None:
        if not self._results:
            return None
        return max(self._results, key=lambda r: r.duration_seconds)
