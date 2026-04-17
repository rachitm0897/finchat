from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from django.core.cache import cache

from apps.core.cache_keys import (
    intent_count_key,
    tool_failure_key,
    tool_latency_key,
    tool_success_key,
)


@dataclass(slots=True)
class ToolExecutionMetric:
    tool_name: str
    ok: bool
    latency_ms: float


class ObservabilityService:
    TOOL_METRICS_TTL = 60 * 60 * 24 * 7
    INTENT_TTL = 60 * 60 * 24 * 30

    def increment_intent(self, intent: str) -> None:
        key = intent_count_key(intent or "unknown")
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=self.INTENT_TTL)

    def record_tool_metric(self, metric: ToolExecutionMetric) -> None:
        latency_key = tool_latency_key(metric.tool_name)
        success_key = tool_success_key(metric.tool_name)
        failure_key = tool_failure_key(metric.tool_name)

        try:
            values = cache.get(latency_key, [])
            values.append(round(metric.latency_ms, 2))
            cache.set(latency_key, values[-500:], timeout=self.TOOL_METRICS_TTL)
        except Exception:
            pass

        counter_key = success_key if metric.ok else failure_key
        try:
            cache.incr(counter_key)
        except ValueError:
            cache.set(counter_key, 1, timeout=self.TOOL_METRICS_TTL)

    def snapshot(self, tool_names: list[str], intents: list[str]) -> dict[str, Any]:
        tools = {}
        for tool_name in tool_names:
            success = int(cache.get(tool_success_key(tool_name), 0) or 0)
            failure = int(cache.get(tool_failure_key(tool_name), 0) or 0)
            latencies = cache.get(tool_latency_key(tool_name), []) or []
            total = success + failure
            avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
            tools[tool_name] = {
                "success_count": success,
                "failure_count": failure,
                "success_rate": round(success / total, 4) if total else 0.0,
                "failure_rate": round(failure / total, 4) if total else 0.0,
                "avg_latency_ms": avg_latency,
                "samples": len(latencies),
            }

        query_distribution = {
            intent: int(cache.get(intent_count_key(intent), 0) or 0)
            for intent in intents
        }

        total_queries = sum(query_distribution.values())
        return {
            "tools": tools,
            "query_distribution": query_distribution,
            "total_queries": total_queries,
        }


@contextmanager
def timed_tool_execution(tool_name: str):
    started = time.perf_counter()
    ok = False
    try:
        yield
        ok = True
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        ObservabilityService().record_tool_metric(
            ToolExecutionMetric(tool_name=tool_name, ok=ok, latency_ms=elapsed_ms)
        )