"""Candle-quality assessment and price-action patterns."""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Optional, Sequence

from app.feed.client import Candle


@dataclass
class CandleQuality:
    score: float                 # 0..1, higher = cleaner directional candle
    body_ratio: float
    upper_wick_ratio: float
    lower_wick_ratio: float
    range_atr: float
    direction: str               # UP | DOWN | NEUTRAL
    engulfing: bool = False
    rejection: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 3),
            "body_ratio": round(self.body_ratio, 3),
            "upper_wick_ratio": round(self.upper_wick_ratio, 3),
            "lower_wick_ratio": round(self.lower_wick_ratio, 3),
            "range_atr": round(self.range_atr, 3),
            "direction": self.direction,
            "is_engulfing": self.engulfing,
            "is_rejection": self.rejection,
            "reason": self.reason,
        }


def assess_candle(candles: Sequence[Candle], atr_value: Optional[float] = None,
                   index: int = -1) -> CandleQuality:
    """Score the candle at `index` (default: last closed candle)."""
    if not candles:
        return CandleQuality(0, 0, 0, 0, 0, "NEUTRAL", reason="no data")
    i = index if index >= 0 else len(candles) - 1
    c = candles[i]
    rng = c.high - c.low
    body = abs(c.close - c.open)
    upper = c.high - max(c.open, c.close)
    lower = min(c.open, c.close) - c.low
    if rng <= 0:
        return CandleQuality(0, 0, 0, 0, 0, "NEUTRAL", reason="zero range")
    body_ratio = body / rng
    upper_ratio = upper / rng
    lower_ratio = lower / rng
    direction = "UP" if c.close > c.open else ("DOWN" if c.close < c.open else "NEUTRAL")

    if atr_value and atr_value > 0:
        range_atr = rng / atr_value
    else:
        range_atr = 0.0

    # base score: reward a decisive body, penalise long wicks / indecision
    score = min(1.0, body_ratio)
    if upper_ratio > 0.4 or lower_ratio > 0.4:
        score *= 0.65
    if body_ratio < 0.2:
        score *= 0.5
    if range_atr > 2.5:
        score *= 0.7
    if range_atr > 4.0:
        score *= 0.6
    score = max(0.0, min(1.0, score))

    engulfing = False
    rejection = False
    reason = "clean body" if body_ratio >= 0.6 else ("indecisive" if body_ratio < 0.2 else "mixed body")
    if i >= 1:
        prev = candles[i - 1]
        prev_body = abs(prev.close - prev.open)
        if (c.close > c.open and prev.close < prev.open and c.close >= prev.open and c.open <= prev.close
                and body > prev_body):
            engulfing = True
        if (c.close < c.open and prev.close > prev.open and c.close <= prev.open and c.open >= prev.close
                and body > prev_body):
            engulfing = True
        if engulfing:
            reason = "engulfing"
            score = min(1.0, score + 0.15)
        # rejection: long wick against the candle direction
        if direction == "UP" and lower_ratio >= 0.4:
            rejection = True
            reason = "lower-wick rejection"
        elif direction == "DOWN" and upper_ratio >= 0.4:
            rejection = True
            reason = "upper-wick rejection"

    return CandleQuality(score, body_ratio, upper_ratio, lower_ratio, range_atr,
                          direction, engulfing, rejection, reason)


def recent_swing_levels(candles: Sequence[Candle], left: int = 2, right: int = 2,
                         lookback: int = 60) -> dict:
    """Nearest confirmed swing high / low levels to the last close."""
    from app.indicators.technical import swing_points
    if len(candles) < left + right + 5:
        return {"available": False}
    window = list(candles[-lookback:])
    highs = [c.high for c in window]
    lows = [c.low for c in window]
    sh, sl = swing_points(highs, lows, left, right)
    last = window[-1].close
    highs_list = [(i, v) for i, v in enumerate(sh) if v is not None]
    lows_list = [(i, v) for i, v in enumerate(sl) if v is not None]
    nearest_high = min(highs_list, key=lambda t: abs(t[1] - last)) if highs_list else None
    nearest_low = min(lows_list, key=lambda t: abs(t[1] - last)) if lows_list else None
    return {
        "available": bool(highs_list and lows_list),
        "nearest_high": nearest_high[1] if nearest_high else None,
        "nearest_high_age": len(window) - 1 - nearest_high[0] if nearest_high else None,
        "nearest_low": nearest_low[1] if nearest_low else None,
        "nearest_low_age": len(window) - 1 - nearest_low[0] if nearest_low else None,
    }


def directional_consistency(candles: Sequence[Candle], lookback: int = 10) -> Optional[float]:
    """Fraction of the last `lookback` candles closing in the dominant direction."""
    if len(candles) < lookback:
        return None
    window = candles[-lookback:]
    ups = sum(1 for c in window if c.close > c.open)
    downs = sum(1 for c in window if c.close < c.open)
    total = ups + downs
    if total == 0:
        return None
    return max(ups, downs) / total


def recent_range(high: Sequence[float], low: Sequence[float], lookback: int = 20) -> Optional[float]:
    if len(high) < lookback:
        return None
    return max(high[-lookback:]) - min(low[-lookback:])


def stdev(values: Sequence[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else 0.0
