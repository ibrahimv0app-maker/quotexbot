"""Canonical symbol registry, alias normalisation and per-symbol health tracking.

Validated API facts (see docs/VALIDATION.md):
  * REST /api/public/candles returns canonical symbols: "EURUSD-OTC".
  * The SSE stream returns symbols with a trailing "q": "EURUSD-OTCq".
  * The WebSocket stream returns canonical symbols: "EURUSD-OTC".
Only the SSE quirk is normalised, and only by stripping a single trailing "q"
that is present on an otherwise known canonical symbol. No other aliasing is
performed - USDBRL-OTC, USDBRL-OTCq and BRLUSD-OTC are treated as distinct.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional



class SymbolState(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"   # streaming but history unavailable
    BROKEN = "broken"       # endpoint returns an error
    STALE = "stale"         # no fresh ticks


@dataclass
class SymbolHealth:
    symbol: str
    state: SymbolState = SymbolState.UNKNOWN
    last_tick_ts: float = 0.0
    last_tick_price: Optional[float] = None
    last_history_ts: float = 0.0
    history_error: str = ""
    tick_count: int = 0
    error_count: int = 0
    last_error: str = ""
    first_seen: float = field(default_factory=time.time)
    validated_at: Optional[float] = None

    @property
    def tick_age(self) -> float:
        return time.time() - self.last_tick_ts if self.last_tick_ts else float("inf")

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "state": self.state.value,
            "tick_age_seconds": round(self.tick_age, 2) if self.last_tick_ts else None,
            "last_tick_ts": self.last_tick_ts or None,
            "last_price": self.last_tick_price,
            "history_age_seconds": round(time.time() - self.last_history_ts, 1) if self.last_history_ts else None,
            "history_error": self.history_error or None,
            "tick_count": self.tick_count,
            "error_count": self.error_count,
            "last_error": self.last_error or None,
            "validated_at": self.validated_at,
        }


class SymbolRegistry:
    """Holds canonical symbols plus live health, and normalises feed aliases."""

    def __init__(self, symbols: Iterable[str]):
        self._canonical: List[str] = list(dict.fromkeys(s.strip().upper() for s in symbols if s.strip()))
        self._health: Dict[str, SymbolHealth] = {s: SymbolHealth(symbol=s) for s in self._canonical}
        self._alias_cache: Dict[str, str] = {}

    # ---------------- canonical set ----------------
    @property
    def symbols(self) -> List[str]:
        return list(self._canonical)

    def __contains__(self, symbol: str) -> bool:
        return symbol in self._health

    def health(self, symbol: str) -> SymbolHealth:
        return self._health.setdefault(symbol, SymbolHealth(symbol=symbol))

    def healthy_symbols(self) -> List[str]:
        return [s for s, h in self._health.items() if h.state in (SymbolState.HEALTHY, SymbolState.DEGRADED)]

    # ---------------- alias normalisation ----------------
    def normalise(self, raw_symbol: str) -> Optional[str]:
        """Map a feed symbol to a canonical symbol, or None if unknown.

        Only two documented forms are accepted:
          1. exact canonical match
          2. canonical + trailing 'q'  (SSE transport quirk)
        """
        if not raw_symbol:
            return None
        raw = raw_symbol.strip()
        if raw in self._health:
            return raw
        cached = self._alias_cache.get(raw)
        if cached is not None:
            return cached
        if raw.endswith("q") and raw[:-1] in self._health:
            canonical = raw[:-1]
            self._alias_cache[raw] = canonical
            return canonical
        return None

    # ---------------- health updates ----------------
    def record_tick(self, raw_symbol: str, price: float, ts: float) -> Optional[str]:
        canonical = self.normalise(raw_symbol)
        if canonical is None:
            h = None
        else:
            h = self.health(canonical)
            h.last_tick_ts = ts
            h.last_tick_price = price
            h.tick_count += 1
            if h.state in (SymbolState.UNKNOWN, SymbolState.STALE, SymbolState.DEGRADED, SymbolState.BROKEN):
                h.state = SymbolState.HEALTHY
        return canonical

    def record_history_ok(self, symbol: str, last_ts: float) -> None:
        h = self.health(symbol)
        h.last_history_ts = time.time()
        h.history_error = ""
        h.validated_at = time.time()
        if h.state in (SymbolState.UNKNOWN, SymbolState.BROKEN, SymbolState.STALE):
            h.state = SymbolState.HEALTHY if h.last_tick_ts else SymbolState.DEGRADED

    def record_history_error(self, symbol: str, error: str) -> None:
        h = self.health(symbol)
        h.history_error = error[:200]
        h.error_count += 1
        h.last_error = error[:200]
        h.validated_at = time.time()
        if h.state is not SymbolState.HEALTHY:
            h.state = SymbolState.BROKEN

    def mark_stale(self) -> None:
        now = time.time()
        for h in self._health.values():
            if h.state in (SymbolState.HEALTHY, SymbolState.DEGRADED) and h.last_tick_ts:
                if now - h.last_tick_ts > 15:
                    h.state = SymbolState.STALE

    def snapshot(self) -> List[dict]:
        return [h.to_dict() for h in sorted(self._health.values(), key=lambda x: x.symbol)]

    def summary(self) -> dict:
        counts: Dict[str, int] = {}
        for h in self._health.values():
            counts[h.state.value] = counts.get(h.state.value, 0) + 1
        return {
            "total": len(self._health),
            "by_state": counts,
            "healthy": counts.get("healthy", 0),
            "streamed": sum(1 for h in self._health.values() if h.tick_count),
        }

    def chunks(self, size: int) -> List[List[str]]:
        """Split symbols into groups of <= `size` for per-connection limits."""
        if size <= 0:
            raise ValueError("size must be positive")
        return [self._canonical[i:i + size] for i in range(0, len(self._canonical), size)]
