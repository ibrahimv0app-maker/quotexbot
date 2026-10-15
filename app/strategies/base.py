"""Strategy base classes, shared context and candidate model."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from app.feed.client import Candle
from app.indicators.patterns import CandleQuality, assess_candle, directional_consistency


@dataclass
class MarketContext:
    """Everything a strategy is allowed to look at, all of it past or present."""
    symbol: str
    now: float
    candles: List[Candle]                 # closed candles only, oldest -> newest
    forming: Optional[Candle] = None      # current, still-forming candle
    last_price: Optional[float] = None
    m5_candles: List[Candle] = field(default_factory=list)
    atr14: Optional[float] = None
    atr_pct: Optional[float] = None
    atr_norm: Optional[float] = None
    vol_stability: Optional[float] = None
    candle_quality: Optional[CandleQuality] = None
    consistency: Optional[float] = None
    data_age: float = 0.0
    last_received_ts: Optional[float] = None

    @property
    def closes(self) -> List[float]:
        return [c.close for c in self.candles]

    @property
    def highs(self) -> List[float]:
        return [c.high for c in self.candles]

    @property
    def lows(self) -> List[float]:
        return [c.low for c in self.candles]

    @property
    def opens(self) -> List[float]:
        return [c.open for c in self.candles]

    @property
    def last_candle(self) -> Optional[Candle]:
        return self.candles[-1] if self.candles else None

    @property
    def price(self) -> float:
        if self.last_price is not None:
            return self.last_price
        return self.candles[-1].close if self.candles else 0.0

    @property
    def has_history(self) -> bool:
        return len(self.candles) >= 30


@dataclass
class Candidate:
    """A strategy's opinion about a symbol, before global filtering/ranking."""
    symbol: str
    strategy: str
    direction: str                      # CALL | PUT
    setup_score: float                  # 0..1, strategy-specific quality
    reasons: List[str] = field(default_factory=list)
    filters_passed: List[str] = field(default_factory=list)
    details: Dict = field(default_factory=dict)
    invalidated: bool = False
    invalid_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol, "strategy": self.strategy, "direction": self.direction,
            "setup_score": round(self.setup_score, 4), "reasons": self.reasons,
            "filters_passed": self.filters_passed, "details": self.details,
            "invalidated": self.invalidated, "invalid_reason": self.invalid_reason,
        }


class Strategy(ABC):
    """A strategy is a pure function of (MarketContext) -> Optional[Candidate]."""

    name: str = "base"
    requires_m5: bool = False
    min_candles: int = 60

    @abstractmethod
    def evaluate(self, ctx: MarketContext) -> Optional[Candidate]:
        """Return a candidate when the entry conditions are met, else None."""

    # helpers -------------------------------------------------------------
    def _candles_ok(self, ctx: MarketContext) -> bool:
        if len(ctx.candles) < self.min_candles:
            return False
        if self.requires_m5 and len(ctx.m5_candles) < 10:
            return False
        return True

    def _make(self, ctx: MarketContext, direction: str, setup_score: float,
              reasons: List[str], details: Optional[Dict] = None) -> Candidate:
        return Candidate(symbol=ctx.symbol, strategy=self.name, direction=direction,
                         setup_score=max(0.0, min(1.0, setup_score)), reasons=reasons,
                         details=details or {})


def build_context(symbol: str, now: float, candles: Sequence[Candle],
                  forming: Optional[Candle] = None, last_price: Optional[float] = None,
                  m5_candles: Optional[Sequence[Candle]] = None,
                  atr_value: Optional[float] = None, atr_pct_value: Optional[float] = None,
                  atr_norm_value: Optional[float] = None, vol_stability_value: Optional[float] = None,
                  data_age: float = 0.0, last_received_ts: Optional[float] = None) -> MarketContext:
    """Assemble a MarketContext, computing derived indicators once."""
    from app.indicators.volatility import atr_pct, normalised_atr, volatility_stability

    candles = list(candles)
    candles = [c for c in candles if c.close_time <= now]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    closes = [c.close for c in candles]
    from app.indicators.technical import atr
    if atr_value is None and candles:
        atr_value = atr(highs, lows, closes)[-1]
    quality = assess_candle(candles, atr_value) if candles else None
    return MarketContext(
        symbol=symbol,
        now=now,
        candles=candles,
        forming=forming,
        last_price=last_price,
        m5_candles=list(m5_candles or []),
        atr14=atr_value,
        atr_pct=atr_pct_value if atr_pct_value is not None else (atr_pct(highs, lows, closes)[-1] if candles else None),
        atr_norm=atr_norm_value if atr_norm_value is not None else (normalised_atr(highs, lows, closes) if candles else None),
        vol_stability=vol_stability_value if vol_stability_value is not None else (volatility_stability(highs, lows, closes) if len(candles) >= 20 else None),
        candle_quality=quality,
        consistency=directional_consistency(candles) if len(candles) >= 10 else None,
        data_age=data_age, last_received_ts=last_received_ts,
    )
