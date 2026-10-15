"""Feed-estimated results using only observations AT OR BEFORE each boundary."""
from __future__ import annotations
import asyncio, time
from dataclasses import dataclass
from typing import Optional
from sqlalchemy import select
from app.database.models import Signal
from app.logging_setup import log_throttled

@dataclass
class OutcomeResult:
    outcome: str
    source: str
    entry_price: Optional[float]
    entry_ts: Optional[int]
    expiry_price: Optional[float]
    expiry_ts: Optional[int]
    note: str = ''
    @property
    def movement(self):
        return None if self.entry_price is None or self.expiry_price is None else self.expiry_price-self.entry_price

def evaluate_direction(direction, entry_price, expiry_price):
    if direction not in ('CALL', 'PUT'): raise ValueError('invalid direction')
    if entry_price == expiry_price: return 'DRAW'
    favorable = expiry_price > entry_price if direction == 'CALL' else expiry_price < entry_price
    return 'WIN' if favorable else 'LOSS'

class OutcomeTracker:
    def __init__(self, settings, db, quotes, telegram, manager):
        self.settings, self.db, self.quotes = settings, db, quotes
        self.telegram, self.manager = telegram, manager
        self._tasks = {}
        self._stop = asyncio.Event()
    def schedule(self, sid, symbol, direction, entry_ts, expiry_ts):
        if sid not in self._tasks:
            self._tasks[sid] = asyncio.create_task(self._track(sid, symbol, direction, entry_ts, expiry_ts))
    async def resume_pending(self):
        active = await self.db.get_active_signal()
        if active: self.schedule(active.id, active.symbol, active.direction, active.entry_ts, active.expiry_ts)
        # Results persisted before a crash remain pending, independent of active signals.
        async with self.db.session() as s:
            rows = (await s.execute(select(Signal).where(Signal.status=='resolved',
                Signal.result_delivery_state=='pending'))).scalars().all()
        for sig in rows: await self._notify_result(sig)
        return int(active is not None)
    async def stop(self):
        self._stop.set()
        for t in list(self._tasks.values()): t.cancel()
        await asyncio.gather(*list(self._tasks.values()), return_exceptions=True)
    async def _quote(self, symbol, target, tol):
        # At/just before boundary. Never use a later price as the entry quote.
        mem = self.quotes.at_or_before(symbol, target, tol)
        row = await self.db.find_quote(symbol, target, tol, received_by=target)
        dbq = (row.ts, row.price) if row else None
        return max([q for q in (mem, dbq) if q], default=None, key=lambda q:q[0])
    async def settle(self, sid, now=None):
        now = time.time() if now is None else now
        sig = await self.db.get_signal(sid)
        if not sig or sig.status != 'active' or now < sig.expiry_ts: return False
        entry = await self._quote(sig.symbol, sig.entry_ts, self.settings.ENTRY_QUOTE_TOLERANCE_SECONDS)
        expiry = await self._quote(sig.symbol, sig.expiry_ts, self.settings.EXPIRY_QUOTE_TOLERANCE_SECONDS)
        if not (entry and expiry) and now < sig.expiry_ts + self.settings.RESULT_TIMEOUT_SECONDS:
            return False
        note = ''
        if not entry or not expiry:
            outcome = 'UNVERIFIED'
            note = 'Missing/out-of-tolerance ' + ', '.join(n for n,q in [('entry observation',entry),('expiry observation',expiry)] if not q)
        else: outcome = evaluate_direction(sig.direction, entry[1], expiry[1])
        changed = await self.manager.resolve(sid, outcome, entry_price=entry[1] if entry else None,
            entry_ts=entry[0] if entry else None, expiry_price=expiry[1] if expiry else None,
            expiry_ts=expiry[0] if expiry else None, note=note)
        if changed: await self._notify_result(await self.db.get_signal(sid))
        return changed
    async def _notify_result(self, sig):
        if not await self.manager.claim_delivery(sig.id, result=True): return
        result = OutcomeResult(sig.outcome, 'feed_estimated', sig.entry_price, sig.entry_quote_ts,
                               sig.expiry_price, sig.expiry_quote_ts, sig.outcome_note or '')
        stats=await self.db.aggregate_outcomes('bt_paper' if self.settings.DRY_RUN else 'bt_live')
        ok = True if self.settings.DRY_RUN else await self.telegram.send_result(sig, result,stats=stats)
        await self.db.update_signal(sig.id, result_delivery_state='paper' if self.settings.DRY_RUN else ('sent' if ok else 'uncertain'))
    async def _track(self, sid, symbol, direction, entry_ts, expiry_ts):
        try:
            while not self._stop.is_set():
                try:
                    if await self.settle(sid): return
                    sig = await self.db.get_signal(sid)
                    if not sig or sig.status != 'active': return
                except asyncio.CancelledError: raise
                except Exception as e: log_throttled('outcome:'+sid,'outcome.retry', error_type=type(e).__name__)
                await asyncio.sleep(1)
        finally: self._tasks.pop(sid, None)
