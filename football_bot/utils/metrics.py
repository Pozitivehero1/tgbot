"""In-process metrics collector — lightweight counters and gauges."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from football_bot.utils.logger import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """Accumulates runtime metrics and persists them to a JSON file."""

    def __init__(self, metrics_path: str = "data/metrics.json") -> None:
        self._path = metrics_path
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}
        self._timings: dict[str, list[float]] = {}
        self._run_metadata: dict[str, Any] = {
            "started_at": datetime.utcnow().isoformat(),
            "run_mode": "",
        }

    def increment(self, key: str, amount: int = 1) -> None:
        self._counters[key] = self._counters.get(key, 0) + amount

    def gauge(self, key: str, value: float) -> None:
        self._gauges[key] = value

    def record_timing(self, key: str, seconds: float) -> None:
        if key not in self._timings:
            self._timings[key] = []
        self._timings[key].append(seconds)

    def set_run_mode(self, mode: str) -> None:
        self._run_metadata["run_mode"] = mode

    def get_counter(self, key: str) -> int:
        return self._counters.get(key, 0)

    def get_gauge(self, key: str) -> float:
        return self._gauges.get(key, 0.0)

    def summary(self) -> dict[str, Any]:
        timing_summary = {
            k: {
                "count": len(v),
                "total": round(sum(v), 3),
                "avg": round(sum(v) / len(v), 3) if v else 0.0,
                "max": round(max(v), 3) if v else 0.0,
            }
            for k, v in self._timings.items()
        }
        return {
            "metadata": {
                **self._run_metadata,
                "finished_at": datetime.utcnow().isoformat(),
            },
            "counters": self._counters,
            "gauges": self._gauges,
            "timings": timing_summary,
        }

    async def persist(self) -> None:
        """Write the current metrics snapshot to disk."""
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        data = self.summary()
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        logger.info("metrics_persisted", path=self._path, counters=self._counters)

    def log_summary(self) -> None:
        logger.info("run_metrics_summary", **self.summary())
