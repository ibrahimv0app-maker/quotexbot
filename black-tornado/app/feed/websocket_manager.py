"""Multi-connection live stream manager (WebSocket primary, SSE fallback).

Validated server behaviour:
  * Hard limit of 10 symbols per connection. Requesting 11 yields the first 10.
  * WebSocket frames carry canonical symbols: {"symbol": "EURUSD-OTC", ...}
  * SSE frames carry a trailing "q" alias:   {"symbol": "EURUSD-OTCq", ...}
  * Both transports deliver ~1 tick/second/symbol.
"""
from __future__ import annotations

import asyncio
import json
import random
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import httpx
import websockets

from app.config import Settings
from app.feed.symbol_registry import SymbolRegistry
from app.logging_setup import log, log_throttled

TickCallback = Callable[[str, float, int, float], None]   # raw_symbol, price, ts, volume


@dataclass
class ConnectionState:
    index: int
    symbols: List[str]
    transport: str
    connected: bool = False
    last_message_ts: float = 0.0
    reconnect_attempt: int = 0
    messages: int = 0
    last_error: str = ""
    started_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "transport": self.transport,
            "symbols": self.symbols,
            "symbol_count": len(self.symbols),
            "connected": self.connected,
            "messages": self.messages,
            "uptime_seconds": round(time.time() - self.started_at, 1),
            "last_message_age": round(time.time() - self.last_message_ts, 1) if self.last_message_ts else None,
            "reconnect_attempt": self.reconnect_attempt,
            "last_error": self.last_error or None,
        }


class StreamManager:
    """Keeps N live connections alive, each carrying <= max_symbols symbols."""

    def __init__(self, settings: Settings, registry: SymbolRegistry,
                 on_tick: TickCallback, transport: Optional[str] = None):
        self.settings = settings
        self.registry = registry
        self.on_tick = on_tick
        self.transport = (transport or settings.STREAM_TRANSPORT).lower()
        self.connections: List[ConnectionState] = []
        self._tasks: List[asyncio.Task] = []
        self._stop = asyncio.Event()
        self._http: Optional[httpx.AsyncClient] = None
        self.on_reconnect = None
        self._repairs = set()

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        groups = self.registry.chunks(self.settings.MAX_SYMBOLS_PER_CONNECTION)
        if len(groups) > self.settings.WS_MAX_CONNECTIONS:
            log.warning("stream.too_many_connections",
                        groups=len(groups), max_connections=self.settings.WS_MAX_CONNECTIONS)
            groups = groups[: self.settings.WS_MAX_CONNECTIONS]
        self.connections = [ConnectionState(index=i, symbols=g, transport=self.transport)
                            for i, g in enumerate(groups)]
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(20, connect=15.0))
        for state in self.connections:
            self._tasks.append(asyncio.create_task(self._run_connection(state), name=f"conn-{state.index}"))
        log.info("stream.started", transport=self.transport, connections=len(self.connections),
                 symbols=sum(len(c.symbols) for c in self.connections))

    async def stop(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        for task in self._repairs: task.cancel()
        await asyncio.gather(*self._repairs, return_exceptions=True)
        if self._http:
            await self._http.aclose()
            self._http = None
        log.info("stream.stopped")

    # ------------------------------------------------------------------ connection loop
    async def _run_connection(self, state: ConnectionState) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                if state.transport == "ws":
                    await self._run_ws(state)
                else:
                    await self._run_sse(state)
                backoff = 1.0
                state.reconnect_attempt = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                state.last_error = str(exc)[:200]
                state.connected = False
                state.reconnect_attempt += 1
                if state.reconnect_attempt >= 3 and state.transport == "ws":
                    state.transport = "sse"
                log_throttled(f"conn:{state.index}", "stream.connection_error",
                              connection=state.index, error=str(exc)[:200],
                              attempt=state.reconnect_attempt)
            if self._stop.is_set():
                break
            sleep_for = min(backoff * (1 + random.random() * 0.5), 30.0)
            await asyncio.sleep(sleep_for)
            backoff = min(backoff * 2, 30.0)

    async def _run_ws(self, state: ConnectionState) -> None:
        url = self.settings.API_BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        url = f"{url.rstrip('/')}/api/public/stream?symbols={','.join(state.symbols)}"
        async with websockets.connect(
            url,
            open_timeout=20,
            close_timeout=3,
            ping_interval=20,
            ping_timeout=20,
            max_queue=2048,
        ) as ws:
            state.connected = True
            self._repair(state)
            state.last_message_ts = time.time()
            log.info("stream.connected", connection=state.index, transport="ws",
                     symbols=len(state.symbols))
            while not self._stop.is_set():
                raw = await asyncio.wait_for(ws.recv(), timeout=20)
                state.last_message_ts = time.time()
                state.messages += 1
                self._handle_raw(raw, state)
        state.connected = False

    async def _run_sse(self, state: ConnectionState) -> None:
        assert self._http is not None
        url = f"{self.settings.API_BASE_URL.rstrip('/')}/api/public/stream"
        async with self._http.stream("GET", url, params={"symbols": ",".join(state.symbols)}) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"SSE HTTP {resp.status_code}")
            state.connected = True
            self._repair(state)
            state.last_message_ts = time.time()
            log.info("stream.connected", connection=state.index, transport="sse",
                     symbols=len(state.symbols))
            async for line in resp.aiter_lines():
                if self._stop.is_set():
                    break
                text = line.strip()
                if not text or not text.startswith("data:"):
                    continue
                state.last_message_ts = time.time()
                state.messages += 1
                self._handle_raw(text[5:].strip(), state)
        state.connected = False

    def _repair(self, state):
        if self.on_reconnect:
            task = asyncio.create_task(self.on_reconnect(state.symbols))
            self._repairs.add(task)
            task.add_done_callback(self._repair_done)

    def _repair_done(self, task):
        self._repairs.discard(task)
        if not task.cancelled() and task.exception():
            log_throttled("repair", "stream.history_repair_failed", error_type=type(task.exception()).__name__)

    # ------------------------------------------------------------------ parsing
    def _handle_raw(self, raw: str, state: ConnectionState) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            log_throttled(f"conn:{state.index}:json", "stream.bad_json",
                          connection=state.index, sample=raw[:120])
            return
        if not isinstance(data, dict):
            return
        raw_symbol = data.get("symbol")
        price = data.get("price")
        ts = data.get("timestamp")
        volume = data.get("volume", 0)
        if raw_symbol is None or price is None or ts is None:
            return
        try:
            price = float(price)
            ts = int(ts)
            volume = float(volume or 0)
        except (TypeError, ValueError):
            return
        if price <= 0:
            return
        try:
            self.on_tick(raw_symbol, price, ts, volume)
        except Exception as exc:  # noqa: BLE001
            log_throttled(f"conn:{state.index}:cb", "stream.callback_error", error=str(exc)[:180])

    # ------------------------------------------------------------------ status
    def status(self) -> dict:
        return {
            "transport": self.transport,
            "connections": [c.to_dict() for c in self.connections],
            "connected": sum(1 for c in self.connections if c.connected),
            "total_connections": len(self.connections),
            "total_messages": sum(c.messages for c in self.connections),
            "symbols": sum(len(c.symbols) for c in self.connections),
            "connected_subscriptions": sum(len(c.symbols) for c in self.connections if c.connected),
        }
