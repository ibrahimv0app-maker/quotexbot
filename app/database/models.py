"""SQLAlchemy 2.0 async models (PostgreSQL in production, SQLite for local/tests)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Float, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


def _json_type():
    """JSONB on PostgreSQL, generic JSON elsewhere (SQLite)."""
    return JSON().with_variant(JSONB, "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Candle(Base):
    __tablename__ = "candles"
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    time: Mapped[int] = mapped_column(Integer, primary_key=True)
    interval: Mapped[str] = mapped_column(String(8), default="1m")
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="rest")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_candles_symbol_time", "symbol", "time"),)


class PairHealth(Base):
    __tablename__ = "pair_health"
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    state: Mapped[str] = mapped_column(String(16), default="unknown")
    last_tick_ts: Mapped[float] = mapped_column(Float, default=0.0)
    last_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_history_ts: Mapped[float] = mapped_column(Float, default=0.0)
    tick_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    signal_no: Mapped[int] = mapped_column(Integer, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    direction: Mapped[str] = mapped_column(String(8))            # CALL | PUT
    strategy: Mapped[str] = mapped_column(String(48), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    score_components: Mapped[dict] = mapped_column(_json_type(), default=dict)
    reasons: Mapped[list] = mapped_column(_json_type(), default=list)
    filters_passed: Mapped[list] = mapped_column(_json_type(), default=list)
    entry_ts: Mapped[int] = mapped_column(Integer, index=True)   # intended entry (epoch)
    expiry_ts: Mapped[int] = mapped_column(Integer)              # intended expiry (epoch)
    sent_ts: Mapped[int] = mapped_column(Integer, default=0)      # telegram send time
    decision_ts: Mapped[int] = mapped_column(Integer, default=0)
    decision_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_quote_ts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expiry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    expiry_quote_ts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)  # active|resolved
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)  # WIN|LOSS|DRAW|UNVERIFIED
    outcome_source: Mapped[str | None] = mapped_column(String(24), nullable=True)  # feed_estimated|manual
    manual_outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
    manual_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_state: Mapped[str] = mapped_column(String(20), default="reserved")
    result_delivery_state: Mapped[str] = mapped_column(String(20), default="pending")
    outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot: Mapped[dict] = mapped_column(_json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (
        # A given entry slot may only ever be used once.
        UniqueConstraint("entry_ts", name="uq_signals_entry_ts"),
        Index("ix_signals_status_created", "status", "created_at"),
    )


class CandidateDiagnostic(Base):
    __tablename__ = "candidate_diagnostics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_ts: Mapped[int] = mapped_column(Integer, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    strategy: Mapped[str] = mapped_column(String(48), index=True)
    direction: Mapped[str | None] = mapped_column(String(8), nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    components: Mapped[dict] = mapped_column(_json_type(), default=dict)
    rejected_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QuoteObservation(Base):
    __tablename__ = "quote_observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    ts: Mapped[int] = mapped_column(Integer, index=True)
    price: Mapped[float] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(8), default="stream")
    received_ts: Mapped[float] = mapped_column(Float, default=__import__("time").time)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_quotes_symbol_ts", "symbol", "ts"),)


class StrategyStat(Base):
    __tablename__ = "strategy_stats"
    strategy: Mapped[str] = mapped_column(String(48), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    trades: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    unverified: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SystemEvent(Base):
    __tablename__ = "system_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    level: Mapped[str] = mapped_column(String(12), default="info", index=True)
    event: Mapped[str] = mapped_column(String(64), index=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class SignalLock(Base):
    """Single-row table used as a cross-process mutual exclusion point."""
    __tablename__ = "signal_lock"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    locked_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    acquired_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(String(160), nullable=True)

class SystemControl(Base):
    __tablename__ = 'system_control'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)

class SchemaVersion(Base):
    __tablename__ = 'schema_version'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
