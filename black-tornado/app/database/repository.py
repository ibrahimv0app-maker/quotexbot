"""Async repository layer - all DB access goes through here."""
from __future__ import annotations

import time
from typing import List, Optional, Sequence

from sqlalchemy import delete, func, insert, select, update, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.database.models import (
    Base, Candle, CandidateDiagnostic, PairHealth, QuoteObservation,
    Signal, SignalLock, StrategyStat, SystemEvent,
)
from app.logging_setup import log


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._engine = None
        self._sessionmaker: Optional[async_sessionmaker] = None

    async def connect(self) -> None:
        url = self.settings.DATABASE_URL
        kwargs = {"echo": self.settings.DB_ECHO, "future": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        else:
            kwargs["pool_size"] = self.settings.DB_POOL_SIZE
            kwargs["pool_pre_ping"] = True
            kwargs["max_overflow"] = 5
        self._engine = create_async_engine(url, **kwargs)
        self._sessionmaker = async_sessionmaker(self._engine, expire_on_commit=False, class_=AsyncSession)
        async with self._engine.begin() as conn:
            if not self.settings.is_sqlite:
                await conn.execute(text("SELECT pg_advisory_xact_lock(18379104)"))
            await conn.run_sync(Base.metadata.create_all)
            from app.database.models import SchemaVersion, SystemControl
            factory = sqlite_insert
            if not self.settings.is_sqlite:
                from sqlalchemy.dialects.postgresql import insert as factory
            await conn.execute(factory(SchemaVersion).values(id=1,version=1).on_conflict_do_nothing(index_elements=["id"]))
            version = (await conn.execute(select(SchemaVersion.version).where(SchemaVersion.id==1))).scalar()
            if version != 1: raise RuntimeError("Unsupported schema version; explicit migration required")
            await conn.execute(factory(SystemControl).values(id=1,paused=False).on_conflict_do_nothing(index_elements=["id"]))
        log.info("database.connected", backend="sqlite" if self.settings.is_sqlite else "postgresql")

    async def disconnect(self) -> None:
        if self._engine:
            await self._engine.dispose()
            self._engine = None

    @property
    def session(self) -> async_sessionmaker:
        if self._sessionmaker is None:
            raise RuntimeError("Database.connect() has not been called")
        return self._sessionmaker

    # ------------------------------------------------------------------ candles
    async def upsert_candles(self, rows: Sequence[dict]) -> int:
        if not rows: return 0
        factory = sqlite_insert
        if not self.settings.is_sqlite:
            from sqlalchemy.dialects.postgresql import insert as factory
        async with self.session() as s, s.begin():
            # Small batches keep SQL compilation and driver work from monopolising
            # the event loop while startup history is being repaired.
            for offset in range(0,len(rows),128):
                stmt = factory(Candle).values(rows[offset:offset+128])
                stmt = stmt.on_conflict_do_update(index_elements=["symbol","time"],
                    set_={c:getattr(stmt.excluded,c) for c in
                          ("open","high","low","close","volume","source","interval")})
                await s.execute(stmt)
        return len(rows)

    async def load_candles(self, symbol: str, limit: int = 2500, interval: str = "1m") -> List[Candle]:
        async with self.session() as s:
            res = await s.execute(
                select(Candle).where(Candle.symbol == symbol, Candle.interval == interval)
                .order_by(Candle.time.desc()).limit(limit)
            )
            rows = list(res.scalars())
        return list(reversed(rows))

    async def candle_count(self, symbol: str) -> int:
        async with self.session() as s:
            res = await s.execute(select(func.count()).select_from(Candle).where(Candle.symbol == symbol))
            return int(res.scalar() or 0)

    # ------------------------------------------------------------------ quotes
    async def insert_quote(self, symbol: str, ts: int, price: float, volume: float = 0.0,
                           source: str = "stream", received_ts=None) -> None:
        async with self.session() as s:
            s.add(QuoteObservation(symbol=symbol, ts=ts, price=price, volume=volume, source=source,
                                   received_ts=time.time() if received_ts is None else received_ts))
            await s.commit()

    async def insert_quotes(self, rows: Sequence[dict]) -> int:
        if not rows:
            return 0
        async with self.session() as s:
            await s.execute(insert(QuoteObservation).values(rows))
            await s.commit()
        return len(rows)

    async def find_quote(self, symbol: str, target_ts: int, tolerance: int, received_by=None) -> Optional[QuoteObservation]:
        """Nearest observation to target_ts within +/- tolerance seconds."""
        async with self.session() as s:
            res = await s.execute(
                select(QuoteObservation)
                .where(QuoteObservation.symbol == symbol,
                       QuoteObservation.ts >= target_ts - tolerance,
                       QuoteObservation.ts <= target_ts,
                       QuoteObservation.received_ts <= (received_by if received_by is not None else time.time()))
                .order_by(QuoteObservation.ts.desc(), QuoteObservation.id.desc()).limit(1)
            )
            return res.scalars().first()

    async def purge_quotes(self, older_than_ts: int) -> int:
        async with self.session() as s:
            res = await s.execute(delete(QuoteObservation).where(QuoteObservation.ts < older_than_ts))
            await s.commit()
            return res.rowcount or 0

    # ------------------------------------------------------------------ signals
    async def create_signal(self, **kwargs) -> Signal:
        async with self.session() as s:
            sig = Signal(**kwargs)
            s.add(sig)
            await s.commit()
            await s.refresh(sig)
            return sig

    async def get_signal(self, signal_id: str) -> Optional[Signal]:
        async with self.session() as s:
            res = await s.execute(select(Signal).where(Signal.id == signal_id))
            return res.scalars().first()

    async def get_active_signal(self) -> Optional[Signal]:
        async with self.session() as s:
            res = await s.execute(select(Signal).where(Signal.status == "active").order_by(Signal.entry_ts))
            return res.scalars().first()

    async def update_signal(self, signal_id: str, **fields) -> None:
        if not fields:
            return
        async with self.session() as s:
            await s.execute(update(Signal).where(Signal.id == signal_id).values(**fields))
            await s.commit()

    async def count_signals(self) -> int:
        async with self.session() as s:
            res = await s.execute(select(func.count()).select_from(Signal))
            return int(res.scalar() or 0)

    async def next_signal_no(self) -> int:
        async with self.session() as s:
            res = await s.execute(select(func.max(Signal.signal_no)))
            return int(res.scalar() or 0) + 1

    async def recent_signals(self, limit: int = 25) -> List[dict]:
        async with self.session() as s:
            res = await s.execute(select(Signal).order_by(Signal.created_at.desc()).limit(limit))
            return [
                {
                    "id": s_.id, "signal_no": s_.signal_no, "symbol": s_.symbol,
                    "direction": s_.direction, "strategy": s_.strategy, "score": s_.score,
                    "entry_ts": s_.entry_ts, "expiry_ts": s_.expiry_ts, "status": s_.status,
                    "outcome": s_.outcome, "outcome_source": s_.outcome_source,
                    "notified": s_.notified, "delivery_state": s_.delivery_state,
                    "result_delivery_state": s_.result_delivery_state, "outcome_note": s_.outcome_note,
                    "manual_outcome": s_.manual_outcome,
                }
                for s_ in res.scalars()
            ]

    # ------------------------------------------------------------------ lock
    async def acquire_lock(self, signal_id: str, note: str = "") -> bool:
        """Atomically take the global signal lock. Returns False if held."""
        async with self.session() as s:
            try:
                if self.settings.is_sqlite:
                    res = await s.execute(
                        update(SignalLock).where(SignalLock.id == 1, SignalLock.locked_by.is_(None))
                        .values(locked_by=signal_id, acquired_at=time.time(), note=note)
                    )
                else:
                    res = await s.execute(
                        update(SignalLock).where(SignalLock.id == 1, SignalLock.locked_by.is_(None))
                        .values(locked_by=signal_id, acquired_at=time.time(), note=note)

                    )
                await s.commit()
                acquired = (res.rowcount or 0) > 0
            except Exception:
                await s.rollback()
                raise
        if acquired:
            log.info("lock.acquired", signal_id=signal_id)
        return acquired

    async def release_lock(self, signal_id: str) -> None:
        async with self.session() as s:
            await s.execute(
                update(SignalLock).where(SignalLock.id == 1, SignalLock.locked_by == signal_id)
                .values(locked_by=None, acquired_at=None, note=None)
            )
            await s.commit()
        log.info("lock.released", signal_id=signal_id)

    async def lock_state(self) -> dict:
        async with self.session() as s:
            res = await s.execute(select(SignalLock).where(SignalLock.id == 1))
            row = res.scalars().first()
            if row is None:
                return {"locked": False, "locked_by": None, "acquired_at": None}
            return {
                "locked": row.locked_by is not None,
                "locked_by": row.locked_by,
                "acquired_at": row.acquired_at,
                "note": row.note,
            }

    async def ensure_lock_row(self) -> None:
        factory = sqlite_insert
        if not self.settings.is_sqlite:
            from sqlalchemy.dialects.postgresql import insert as factory
        async with self.session() as s:
            await s.execute(factory(SignalLock).values(id=1).on_conflict_do_nothing(index_elements=["id"]))
            await s.commit()

    # ------------------------------------------------------------------ stats
    async def bump_strategy_stat(self, strategy: str, symbol: str, outcome: str) -> None:
        async with self.session() as s:
            res = await s.execute(select(StrategyStat).where(
                StrategyStat.strategy == strategy, StrategyStat.symbol == symbol))
            row = res.scalars().first()
            if row is None:
                row = StrategyStat(strategy=strategy, symbol=symbol, trades=0, wins=0, losses=0, draws=0, unverified=0)
                s.add(row)
            row.trades += 1
            if outcome == "WIN":
                row.wins += 1
            elif outcome == "LOSS":
                row.losses += 1
            elif outcome == "DRAW":
                row.draws += 1
            else:
                row.unverified += 1
            await s.commit()

    async def strategy_stats(self) -> List[dict]:
        async with self.session() as s:
            res = await s.execute(select(StrategyStat).order_by(StrategyStat.strategy, StrategyStat.symbol))
            out = []
            for r in res.scalars():
                decided = r.wins + r.losses
                out.append({
                    "strategy": r.strategy, "symbol": r.symbol, "trades": r.trades,
                    "wins": r.wins, "losses": r.losses, "draws": r.draws, "unverified": r.unverified,
                    "win_rate": round(r.wins / decided * 100, 2) if decided else None,
                })
            return out

    async def aggregate_outcomes(self, scope=None) -> dict:
        if scope not in (None,'bt_paper','bt_live'): raise ValueError('Invalid outcome scope')
        async with self.session() as s:
            stmt=select(Signal.outcome,func.count())
            delivery_stmt=select(func.count()).select_from(Signal).where(Signal.notified.is_(True))
            if scope:
                filters=(Signal.strategy.in_([f'BT{i:02d}' for i in range(1,26)]),Signal.delivery_state==('paper' if scope=='bt_paper' else 'sent'))
                stmt=stmt.where(*filters)
                delivery_stmt=delivery_stmt.where(*filters)
            res=await s.execute(stmt.group_by(Signal.outcome))
            counts = {k or "PENDING": v for k, v in res.all()}
            delivered = int((await s.execute(delivery_stmt)).scalar() or 0)
        wins = counts.get("WIN", 0); losses = counts.get("LOSS", 0)
        decided = wins + losses
        return {
            "total": sum(counts.values()), "signals_delivered": delivered,
            "wins": wins, "losses": losses,
            "draws": counts.get("DRAW", 0),
            "unverified": counts.get("UNVERIFIED", 0),
            "pending": counts.get("PENDING", 0),
            "win_rate": round(wins / decided * 100, 2) if decided else None,
        }

    # ------------------------------------------------------------------ diagnostics
    async def record_candidate(self, cycle_ts: int, symbol: str, strategy: str,
                               score: float, components: dict, direction: str | None = None,
                               rejected_reason: str | None = None) -> None:
        async with self.session() as s:
            s.add(CandidateDiagnostic(cycle_ts=cycle_ts, symbol=symbol, strategy=strategy,
                                      score=score, components=components, direction=direction,
                                      rejected_reason=rejected_reason))
            await s.commit()

    async def record_candidates_bulk(self, rows: Sequence[dict]) -> None:
        if not rows:
            return
        async with self.session() as s:
            await s.execute(insert(CandidateDiagnostic).values(rows))
            await s.commit()

    async def rejected_reasons(self, limit: int = 500) -> List[dict]:
        async with self.session() as s:
            res = await s.execute(
                select(CandidateDiagnostic.rejected_reason, func.count())
                .where(CandidateDiagnostic.rejected_reason.is_not(None))
                .group_by(CandidateDiagnostic.rejected_reason)
                .order_by(func.count().desc()).limit(limit)
            )
            return [{"reason": r, "count": c} for r, c in res.all()]

    # ------------------------------------------------------------------ health / events
    async def upsert_pair_health(self, rows: Sequence[dict]) -> None:
        if not rows:
            return
        async with self.session() as s:
            for r in rows:
                obj = await s.get(PairHealth, r["symbol"])
                if obj is None:
                    obj = PairHealth(symbol=r["symbol"])
                    s.add(obj)
                for k, v in r.items():
                    if k != "symbol":
                        setattr(obj, k, v)
            await s.commit()

    async def pair_health_rows(self) -> List[dict]:
        async with self.session() as s:
            res = await s.execute(select(PairHealth))
            return [
                {"symbol": r.symbol, "state": r.state, "last_tick_ts": r.last_tick_ts,
                 "last_price": r.last_price, "tick_count": r.tick_count,
                 "error_count": r.error_count, "last_error": r.last_error}
                for r in res.scalars()
            ]

    async def log_event(self, level: str, event: str, detail: str | None = None) -> None:
        async with self.session() as s:
            s.add(SystemEvent(level=level, event=event, detail=detail))
            await s.commit()

    async def recent_events(self, limit: int = 50) -> List[dict]:
        async with self.session() as s:
            res = await s.execute(select(SystemEvent).order_by(SystemEvent.created_at.desc()).limit(limit))
            return [{"level": r.level, "event": r.event, "detail": r.detail,
                     "created_at": r.created_at.isoformat() if r.created_at else None}
                    for r in res.scalars()]
