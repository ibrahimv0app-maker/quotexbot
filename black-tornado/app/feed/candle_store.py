"""In-memory candle store with live aggregation, persistence and REST reconciliation.

Candle semantics (validated against the live API):
  * `time` is the candle OPEN timestamp in epoch seconds, always 60s aligned.
  * A candle is CLOSED once `time + 60 <= now`.
  * The REST feed's last element is the still-forming candle - it must never be
    used as a final value by indicators.
  * Live ticks carry the same epoch-second timestamps (1s resolution).
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional

from app.database.repository import Database
from app.feed.client import Candle, FeedClient
from app.logging_setup import log, log_throttled

MAX_CANDLES_IN_MEMORY = 2600
MINUTE = 60


class CandleStore:
    def __init__(self, db: Database, client: FeedClient, interval: str = "1m"):
        self.db = db
        self.client = client
        self.interval = interval
        self._closed: Dict[str, Deque[Candle]] = defaultdict(lambda: deque(maxlen=MAX_CANDLES_IN_MEMORY))
        self._forming: Dict[str, Candle] = {}
        self._last_tick: Dict[str, tuple[int, float]] = {}   # symbol -> (ts, price)
        self._lock = asyncio.Lock()
        self._partial = set()

    # ------------------------------------------------------------------ access
    def closed_candles(self, symbol: str, limit: int | None = None) -> List[Candle]:
        data = list(self._closed.get(symbol, ()))
        return data[-limit:] if limit else data

    def closed_count(self, symbol: str) -> int:
        return len(self._closed.get(symbol, ()))

    def last_closed(self, symbol: str) -> Optional[Candle]:
        data = self._closed.get(symbol)
        return data[-1] if data else None

    def forming(self, symbol: str) -> Optional[Candle]:
        return self._forming.get(symbol)

    def last_price(self, symbol: str) -> Optional[float]:
        v = self._last_tick.get(symbol)
        return v[1] if v else None

    def last_tick_ts(self, symbol: str) -> float:
        v = self._last_tick.get(symbol)
        return float(v[0]) if v else 0.0

    def has_history(self, symbol: str, minimum: int) -> bool:
        return self.closed_count(symbol) >= minimum

    # ------------------------------------------------------------------ ingest
    def apply_tick(self, symbol: str, price: float, ts: int) -> None:
        """Fold a live tick into the forming candle (no repainting of closed bars)."""
        if price is None or price <= 0: return
        bucket = (ts // MINUTE) * MINUTE
        last = self.last_closed(symbol)
        if last and bucket <= last.time: return  # closed bars never repaint from late ticks
        prev = self._last_tick.get(symbol)
        if prev and ts < prev[0]: return
        cur = self._forming.get(symbol)
        if cur is not None and prev and ts-prev[0] > 12:
            self._partial.add((symbol,cur.time))
        if cur is None or cur.time != bucket:
            if ts-bucket > 2:
                self._partial.add((symbol,bucket))
            if cur is not None and cur.time < bucket:
                self._close_forming(symbol, cur)
            self._forming[symbol] = Candle(bucket, price, price, price, price, None)
        else:
            self._forming[symbol] = Candle(cur.time, cur.open, max(cur.high, price), min(cur.low, price), price, None)
        self._last_tick[symbol] = (ts, price)

    def _close_forming(self, symbol: str, candle: Candle) -> None:
        """Promote a forming candle into the closed series (idempotent)."""
        if (symbol,candle.time) in self._partial: return
        series = self._closed[symbol]
        if series and series[-1].time >= candle.time:
            return
        elif not series or series[-1].time < candle.time:
            series.append(candle)

    def roll_over(self, now: Optional[float] = None) -> List[Candle]:
        """Close any forming candle whose minute has elapsed. Returns newly closed bars."""
        now = now or time.time()
        closed: List[Candle] = []
        for symbol, candle in list(self._forming.items()):
            if candle.time + MINUTE <= now:
                self._close_forming(symbol, candle)
                closed.append(candle)
                if self._forming.get(symbol) is candle:
                    del self._forming[symbol]
        return closed

    def merge_candles(self, symbol: str, candles: List[Candle], source: str = "rest") -> int:
        """Merge REST candles (authoritative) into the store; returns rows added/updated."""
        known = {c.time: c for c in self._closed[symbol]}
        count = 0
        for c in candles:
            if c.time + MINUTE > time.time(): continue
            if source == "rest": self._partial.discard((symbol,c.time))
            if known.get(c.time) != c:
                known[c.time] = c
                count += 1
        self._closed[symbol] = deque(sorted(known.values(), key=lambda c:c.time), maxlen=MAX_CANDLES_IN_MEMORY)
        return count

    # ------------------------------------------------------------------ persistence
    async def persist(self, symbol: str, candles: List[Candle], source: str = "rest") -> int:
        if not candles:
            return 0
        rows = []
        for c in candles:
            if c.time + 60 > time.time(): continue
            rows.append({
                "symbol": symbol, "time": c.time, "interval": self.interval,
                "open": c.open, "high": c.high, "low": c.low, "close": c.close,
                "volume": c.volume, "source": source,
            })
        try:
            return await self.db.upsert_candles(rows)
        except Exception as exc:  # noqa: BLE001
            log_throttled("candle.persist", "candle.persist_failed", symbol=symbol, error=str(exc)[:180])
            return 0

    async def load_from_db(self, symbol: str, limit: int = MAX_CANDLES_IN_MEMORY) -> int:
        try:
            rows = await self.db.load_candles(symbol, limit=limit, interval=self.interval)
        except Exception as exc:  # noqa: BLE001
            log.warning("candle.load_db_failed", symbol=symbol, error=str(exc)[:180])
            return 0
        if not rows:
            return 0
        series = deque(sorted((Candle(r.time, r.open, r.high, r.low, r.close, r.volume) for r in rows),
                              key=lambda c: c.time), maxlen=MAX_CANDLES_IN_MEMORY)
        self._closed[symbol] = series
        return len(series)

    # ------------------------------------------------------------------ backfill
    async def backfill(self, symbol: str, limit: int = 2001) -> int:
        try:
            candles = await self.client.get_candles(symbol, interval=self.interval, limit=limit)
        except Exception as exc:  # noqa: BLE001
            log_throttled(f"backfill:{symbol}", "candle.backfill_failed", symbol=symbol, error=str(exc)[:180])
            return 0
        added = self.merge_candles(symbol, candles, source="rest")
        await self.persist(symbol, candles, source="rest")
        return added

    async def reconcile(self, symbol: str, limit: int = 10) -> int:
        """Fetch the newest closed candles from REST and correct the local series."""
        try:
            candles = await self.client.get_candles(symbol, interval=self.interval, limit=limit)
        except Exception as exc:  # noqa: BLE001
            log_throttled(f"reconcile:{symbol}", "candle.reconcile_failed", symbol=symbol, error=str(exc)[:180])
            return 0
        added = self.merge_candles(symbol, candles, source="rest")
        if added:
            await self.persist(symbol, candles, source="rest")
        return added

    # ------------------------------------------------------------------ helpers
    def series(self, symbol: str) -> List[Candle]:
        return list(self._closed.get(symbol, ()))

    def stats(self) -> dict:
        return {
            "symbols_with_history": len(self._closed),
            "total_candles": sum(len(v) for v in self._closed.values()),
            "forming": len(self._forming),
        }
