"""REST client for the Quotex feed API.

Validated behaviour (docs/VALIDATION.md):
  GET {base}/api/public/candles?symbol=SYM&interval=1m&limit=N
    -> {"symbol": str, "interval": str, "count": int,
        "candles": [{"time": int, "open": float, "high": float,
                     "low": float, "close": float, "volume": int}]}

  * `time` is the candle OPEN timestamp, always 60s aligned.
  * `count` never exceeds 2001 even if a bigger limit is requested.
  * The final element is the still-forming candle (open <= now < open+60).
  * An unknown symbol returns HTTP 400 with a Zod-style error array.
  * Nine documented symbols returned HTTP 200 with empty candles during initial
    testing. Availability is rechecked; no prices are substituted.
"""
from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from typing import List, Optional, Sequence

import httpx

from app.logging_setup import log_throttled


class FeedError(RuntimeError):
    """Raised for transport / protocol level failures."""


class SymbolUnavailable(FeedError):
    """Raised when the API reports a symbol as unknown or internally broken."""


@dataclass(frozen=True)
class Candle:
    time: int          # candle OPEN timestamp (epoch seconds, UTC)
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float]  # unvalidated source field; None when unavailable

    @property
    def close_time(self) -> int:
        return self.time + 60

    @property
    def is_closed(self) -> bool:
        return self.time + 60 <= int(time.time())

    def as_dict(self) -> dict:
        return {
            "time": self.time, "open": self.open, "high": self.high,
            "low": self.low, "close": self.close, "volume": self.volume,
        }


def parse_candles(payload: dict, expect_symbol: Optional[str] = None) -> List[Candle]:
    """Strictly parse an API candles payload. Raises on structural problems."""
    if not isinstance(payload, dict):
        raise FeedError("candles payload is not an object")
    if "candles" not in payload:
        raise FeedError("candles payload missing 'candles' key")
    raw = payload["candles"]
    if not isinstance(raw, list):
        raise FeedError("'candles' is not a list")
    if expect_symbol and payload.get("symbol") and payload["symbol"] != expect_symbol:
        raise FeedError(f"symbol mismatch: got {payload['symbol']!r} expected {expect_symbol!r}")

    out: List[Candle] = []
    for item in raw:
        try:
            t = int(item["time"])
            o = float(item["open"]); h = float(item["high"])
            l = float(item["low"]); c = float(item["close"])
            v = float(item["volume"]) if item.get("volume") is not None else None
        except (KeyError, TypeError, ValueError) as exc:
            raise FeedError(f"malformed candle {item!r}: {exc}") from exc
        if not all(math.isfinite(x) for x in (o, h, l, c)) or (v is not None and not math.isfinite(v)):
            raise FeedError("non-finite OHLC value")
        if t <= 0 or t > time.time() + 60:
            raise FeedError("invalid/future candle timestamp")
        if t % 60 != 0:
            raise FeedError(f"candle timestamp {t} is not minute aligned")
        if h < max(o, c) or l > min(o, c) or l > h:
            raise FeedError(f"candle {t} violates OHLC ordering: {item!r}")
        if min(o, h, l, c) <= 0:
            raise FeedError(f"candle {t} has non-positive price: {item!r}")
        out.append(Candle(t, o, h, l, c, v))
    # ordering / duplicate validation
    for i in range(1, len(out)):
        if out[i].time <= out[i - 1].time:
            raise FeedError(f"candles not strictly ascending at index {i} ({out[i-1].time} -> {out[i].time})")
    return out


class FeedClient:
    """Async REST client with bounded concurrency and retry/backoff."""

    def __init__(self, base_url: str, timeout: float = 30.0, max_retries: int = 3, concurrency: int = 6):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers={"accept": "application/json", "user-agent": "quotex-m1-signal-bot/1.0"},
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
        self.max_retries = max_retries
        self._request_sem = asyncio.Semaphore(concurrency)
        self._last_ok_ts = 0.0
        self.request_count = 0
        self.error_count = 0

    async def aclose(self) -> None:
        await self._client.aclose()

    @property
    def last_ok_ts(self) -> float:
        return self._last_ok_ts

    async def _get(self, path: str, params: dict) -> dict:
        async with self._request_sem:
            return await self._get_bounded(path,params)

    async def _get_bounded(self, path: str, params: dict) -> dict:
        url = f"{self.base_url}{path}"
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                self.request_count += 1
                resp = await self._client.get(path, params=params)
                if resp.status_code == 200:
                    self._last_ok_ts = time.time()
                    return resp.json()
                body = resp.text[:300]
                if resp.status_code in (400, 404, 500) and "Unknown symbol" in body:
                    raise SymbolUnavailable(f"unknown symbol: {params.get('symbol')}")
                if resp.status_code == 500:
                    # server-side IndexError for some symbols - permanent-ish
                    raise SymbolUnavailable(f"server error 500 for {params.get('symbol')}: {body}")
                raise FeedError(f"HTTP {resp.status_code} for {url}: {body}")
            except SymbolUnavailable:
                raise
            except (httpx.HTTPError, FeedError, ValueError) as exc:
                last_exc = exc
                sleep = min(2 ** attempt, 8) + (0.1 * attempt)
                log_throttled(f"feed:{url}:{type(exc).__name__}", "feed_request_retry",
                              url=url, attempt=attempt, error=str(exc)[:200])
                await asyncio.sleep(sleep)
        self.error_count += 1
        raise FeedError(f"GET {url} failed after {self.max_retries} attempts: {last_exc}")

    async def get_candles(self, symbol: str, interval: str = "1m", limit: int = 2001) -> List[Candle]:
        payload = await self._get("/api/public/candles",
                                  {"symbol": symbol, "interval": interval, "limit": max(1, min(limit, 2001))})
        return parse_candles(payload, expect_symbol=symbol)

    async def get_candles_many(self, symbols: Sequence[str], interval: str = "1m",
                               limit: int = 2001, concurrency: int = 6) -> dict:
        """Fetch candles for many symbols with bounded concurrency.

        Returns {symbol: (candles, error_or_None)}. One failing symbol never
        aborts the batch - it is reported per symbol.
        """
        sem = asyncio.Semaphore(max(1, concurrency))
        results: dict = {}

        async def one(sym: str):
            async with sem:
                t0 = time.time()
                try:
                    candles = await self.get_candles(sym, interval=interval, limit=limit)
                    results[sym] = (candles, None, round((time.time() - t0) * 1000))
                except Exception as exc:  # noqa: BLE001 - recorded per symbol
                    results[sym] = ([], str(exc)[:200], round((time.time() - t0) * 1000))

        await asyncio.gather(*(one(s) for s in symbols))
        return results

    async def validate_symbol(self, symbol: str) -> dict:
        """Health check for one symbol."""
        t0 = time.time()
        try:
            candles = await self.get_candles(symbol, limit=5)
            last = candles[-1] if candles else None
            return {
                "symbol": symbol, "ok": bool(candles), "error": None if candles else "empty history",
                "latency_ms": round((time.time() - t0) * 1000),
                "candles": len(candles),
                "last_time": last.time if last else None,
                "last_price": last.close if last else None,
                "server_now": int(time.time()),
                "lag_seconds": int(time.time()) - last.time if last else None,
            }
        except Exception as exc:  # noqa: BLE001
            return {"symbol": symbol, "ok": False, "error": str(exc)[:200],
                    "latency_ms": round((time.time() - t0) * 1000)}
