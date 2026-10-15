"""Structured logging setup (rate-limited error spam protection)."""
from __future__ import annotations

import logging
import sys
import time
from collections import defaultdict

import structlog


class RateLimiter:
    """Suppresses repeated identical log messages within a window."""

    def __init__(self, window_seconds: float = 60.0):
        self.window = window_seconds
        self._last: dict[str, float] = defaultdict(float)
        self._counts: dict[str, int] = defaultdict(int)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        if now - self._last[key] > self.window:
            self._last[key] = now
            self._counts[key] = 1
            return True
        self._counts[key] += 1
        return False

    def count(self, key: str) -> int:
        return self._counts[key]


def setup_logging(level: str = "INFO", json_output: bool = True) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=getattr(logging, level.upper(), logging.INFO))

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), logging.INFO)),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


log = structlog.get_logger("qbot")
rate_limiter = RateLimiter(60.0)


def log_throttled(key: str, event: str, level: str = "warning", **kw) -> bool:
    """Log `event` at most once per window for a given key. Returns True if logged."""
    if not rate_limiter.allow(key):
        return False
    getattr(log, level)(event, throttle_key=key, suppressed_count=rate_limiter.count(key), **kw)
    return True
