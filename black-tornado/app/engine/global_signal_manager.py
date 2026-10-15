"""Transactional reservation, persistent singleton lock and idempotent settlement."""
from __future__ import annotations
import time, uuid
from dataclasses import dataclass
from typing import Optional
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from app.database.models import Signal, SignalLock, StrategyStat
from app.database.repository import Database

@dataclass
class PublishResult:
    published: bool
    signal_id: Optional[str] = None
    reason: str = ""
    signal_no: Optional[int] = None

class GlobalSignalManager:
    def __init__(self, db: Database): self.db = db
    async def ensure_initialised(self): await self.db.ensure_lock_row()
    async def is_busy(self):
        return bool((await self.db.lock_state()).get('locked')) or await self.db.get_active_signal() is not None

    async def publish(self, slot, scored, snapshot, decision_ts, decision_price, extra=None):
        if not slot.contains(time.time()):
            return PublishResult(False, reason="notification window missed")
        sid = str(uuid.uuid4())
        try:
            async with self.db.session() as s, s.begin():
                # UPDATE takes a row-level lock on PostgreSQL; all subsequent checks
                # and the signal insert occur in this SAME transaction.
                lock = await s.execute(update(SignalLock).where(
                    SignalLock.id == 1, SignalLock.locked_by.is_(None)).values(
                    locked_by=sid, acquired_at=time.time(), note='reserved'))
                if lock.rowcount != 1: return PublishResult(False, reason='global lock held')
                existing = (await s.execute(select(Signal).where(
                    (Signal.status == 'active') | (Signal.entry_ts == slot.entry_ts)))).scalars().first()
                if existing:
                    await s.rollback()
                    return PublishResult(False, reason='active lifecycle or used entry slot')
                no = int((await s.execute(select(func.max(Signal.signal_no)))).scalar() or 0) + 1
                c = scored.candidate
                row = Signal(id=sid, signal_no=no, symbol=c.symbol, direction=c.direction,
                    strategy=c.strategy, score=scored.score, score_components=scored.components,
                    reasons=c.reasons, filters_passed=c.filters_passed, entry_ts=slot.entry_ts,
                    expiry_ts=slot.expiry_ts, decision_ts=int(decision_ts), decision_price=decision_price,
                    status='active', snapshot={**snapshot, **(extra or {})}, delivery_state='reserved')
                s.add(row)
                await s.flush()
            return PublishResult(True, sid, signal_no=no)
        except IntegrityError:
            return PublishResult(False, reason='duplicate entry rejected')

    async def claim_delivery(self, sid, result=False):
        field = Signal.result_delivery_state if result else Signal.delivery_state
        initial = 'pending' if result else 'reserved'
        async with self.db.session() as s, s.begin():
            r = await s.execute(update(Signal).where(Signal.id == sid, field == initial).values(
                **{field.key: 'attempting'}))
            return r.rowcount == 1

    async def mark_notified(self, sid, ok, error=''):
        await self.db.update_signal(sid, notified=ok, delivery_state='sent' if ok else 'uncertain',
            notify_error=error or None)

    async def resolve(self, sid, outcome, outcome_source='feed_estimated', entry_price=None,
                      entry_ts=None, expiry_price=None, expiry_ts=None, note=''):
        # CAS settlement, aggregate update and lock release in one transaction.
        async with self.db.session() as s, s.begin():
            r = await s.execute(update(Signal).where(Signal.id == sid, Signal.status == 'active').values(
                status='resolved', outcome=outcome, outcome_source=outcome_source,
                entry_price=entry_price, entry_quote_ts=entry_ts, expiry_price=expiry_price,
                expiry_quote_ts=expiry_ts, outcome_note=note))
            if r.rowcount != 1: return False
            sig = await s.get(Signal, sid)
            stat = await s.get(StrategyStat, (sig.strategy, sig.symbol))
            if not stat:
                stat = StrategyStat(strategy=sig.strategy, symbol=sig.symbol, trades=0,
                                    wins=0, losses=0, draws=0, unverified=0)
                s.add(stat)
            stat.trades += 1
            attr = {'WIN':'wins','LOSS':'losses','DRAW':'draws'}.get(outcome, 'unverified')
            setattr(stat, attr, getattr(stat, attr) + 1)
            await s.execute(update(SignalLock).where(SignalLock.id == 1, SignalLock.locked_by == sid)
                            .values(locked_by=None, acquired_at=None, note=None))
        return True
