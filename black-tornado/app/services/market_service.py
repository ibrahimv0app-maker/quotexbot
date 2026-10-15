"""Managed feed intake, history repair, durable raw quotes and closed candles."""
from __future__ import annotations
import asyncio, time, math
from dataclasses import replace
from collections import defaultdict
from app.feed.client import Candle, FeedClient
from app.feed.symbol_registry import SymbolRegistry
from app.feed.candle_store import CandleStore
from app.feed.websocket_manager import StreamManager
from app.engine.quote_buffer import QuoteBuffer
from app.strategies.base import build_context
from app.logging_setup import log_throttled

def aggregate_m5(candles, now):
    buckets = defaultdict(list)
    for c in candles:
        if c.close_time <= now: buckets[(c.time//300)*300].append(c)
    out = []
    for b, items in sorted(buckets.items()):
        if b+300 > now or [c.time for c in items] != list(range(b,b+300,60)): continue
        out.append(Candle(b,items[0].open,max(c.high for c in items),min(c.low for c in items),items[-1].close,None))
    return out

class MarketService:
    def __init__(self, settings, db):
        self.settings, self.db = settings, db
        self.client = FeedClient(settings.API_BASE_URL,concurrency=settings.CANDLE_FETCH_CONCURRENCY)
        self.registry = SymbolRegistry(settings.SYMBOLS)
        self.candles = CandleStore(db,self.client)
        self.quotes = QuoteBuffer(maxlen=1200)
        self.stream = StreamManager(settings,self.registry,self._on_tick)
        self.stream.on_reconnect = self.backfill_all
        self._pending_quotes = []
        self._pending_candles = {}
        self._context_cache = {}
        self.tasks = []
        self.tick_count = 0
        self.invalid_ticks = 0
        self.last_error = None
        self.started = False
        self.last_flush = 0
    def _on_tick(self, raw_symbol, price, ts, volume):
        now = time.time()
        sym = self.registry.normalise(raw_symbol)
        if not sym or not math.isfinite(price) or price <= 0 or ts <= 0 or abs(now-ts)>self.settings.MAX_CLOCK_SKEW_SECONDS:
            self.invalid_ticks += 1
            return
        prev = self.quotes.last_ts(sym)
        if ts < prev: self.invalid_ticks += 1; return
        self.registry.record_tick(raw_symbol,price,ts)
        self.tick_count += 1
        old = self.candles.forming(sym)
        if old and old.time+60 <= ts and (sym,old.time) not in self.candles._partial:
            self._pending_candles[(sym,old.time)] = self._row(sym,old)
        self.quotes.add(sym,ts,price,received_ts=now)
        self.candles.apply_tick(sym,price,ts)
        self._pending_quotes.append(dict(symbol=sym,ts=ts,price=price,volume=None,source='stream',received_ts=now))
    def _row(self,sym,c):
        return dict(symbol=sym,**c.as_dict(),interval='1m',source='stream')
    async def start(self):
        self.started = True
        await self.stream.start()
        self.tasks = [asyncio.create_task(self._maintenance()),asyncio.create_task(self._flusher())]
    async def stop(self):
        self.started = False
        await self.stream.stop()
        for t in self.tasks: t.cancel()
        await asyncio.gather(*self.tasks,return_exceptions=True)
        await self._flush()
        await self.client.aclose()
    async def _flush(self):
        quotes, self._pending_quotes = self._pending_quotes, []
        candles, self._pending_candles = list(self._pending_candles.values()), {}
        try:
            for i in range(0,len(quotes),500): await self.db.insert_quotes(quotes[i:i+500])
            if candles: await self.db.upsert_candles(candles)
            self.last_flush = time.time()
        except Exception:
            self._pending_quotes = quotes + self._pending_quotes
            for c in candles: self._pending_candles[(c['symbol'],c['time'])] = c
            # Bounded memory under extended DB outage; no new signals while backlog exists.
            self._pending_quotes = self._pending_quotes[-100000:]
            raise
    async def _flusher(self):
        while self.started:
            try: await self._flush()
            except Exception as e: log_throttled('flush','database.flush_failed',error_type=type(e).__name__)
            await asyncio.sleep(1)
    async def backfill_all(self, symbols=None, limit=None):
        results = await self.client.get_candles_many(symbols or self.registry.symbols,
            limit=limit or self.settings.CANDLE_BACKFILL_LIMIT, concurrency=self.settings.CANDLE_FETCH_CONCURRENCY)
        summary = {'ok':[], 'unavailable':[]}
        for sym,(candles,err,ms) in results.items():
            if err or not candles:
                self.registry.record_history_error(sym,err or 'empty history')
                summary['unavailable'].append({'symbol':sym,'error':err or 'empty history'})
            else:
                self.candles.merge_candles(sym,candles)
                await self.candles.persist(sym,candles)
                self.registry.record_history_ok(sym,candles[-1].time)
                self._context_cache.pop(sym,None)
                summary['ok'].append(sym)
        return summary
    async def _maintenance(self):
        repaired = time.monotonic()
        while self.started:
            try:
                now = time.time()
                for sym in self.registry.symbols:
                    cur = self.candles.forming(sym)
                    if cur and cur.close_time <= now and (sym,cur.time) not in self.candles._partial: self._pending_candles[(sym,cur.time)] = self._row(sym,cur)
                self.candles.roll_over(now)
                self.registry.mark_stale()
                # Stale/reconnected series cannot qualify until REST repair catches gaps.
                if time.monotonic()-repaired >= self.settings.RECONCILE_INTERVAL_SECONDS:
                    await self.backfill_all(limit=2001)
                    repaired = time.monotonic()
                    await self.db.purge_quotes(int(now)-self.settings.TICK_RETENTION_SECONDS)
                await self.db.upsert_pair_health([dict(symbol=h.symbol,state=h.state.value,
                    last_tick_ts=h.last_tick_ts,last_price=h.last_tick_price,last_history_ts=h.last_history_ts,
                    tick_count=h.tick_count,error_count=h.error_count,last_error=h.last_error) for h in self.registry._health.values()])
            except Exception as e: log_throttled('maintenance','market.maintenance_failed',error_type=type(e).__name__)
            await asyncio.sleep(5)
    def build_context(self,symbol,now=None):
        now = time.time() if now is None else now
        candles = self.candles.closed_candles(symbol,limit=320)
        if len(candles)<30: return None
        key = (candles[-1].time,candles[-1].close,len(candles))
        cached = self._context_cache.get(symbol)
        if not cached or cached[0] != key:
            ctx = build_context(symbol,now,candles,m5_candles=aggregate_m5(candles,now))
            self._context_cache[symbol] = (key,ctx)
        ctx = self._context_cache[symbol][1]
        return replace(ctx,now=now,last_price=self.quotes.last_price(symbol),
            forming=self.candles.forming(symbol),data_age=now-self.quotes.last_ts(symbol),last_received_ts=self.quotes.last_received_ts(symbol))
    def status(self):
        return dict(registry=self.registry.summary(),candles=self.candles.stats(),stream=self.stream.status(),
            tick_count=self.tick_count,invalid_ticks=self.invalid_ticks,quote_backlog=len(self._pending_quotes),last_flush=self.last_flush)
