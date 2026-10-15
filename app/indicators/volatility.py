"""Volatility regime helpers: ATR normalisation, squeeze detection, stability."""
from __future__ import annotations

import statistics
from typing import List, Optional, Sequence

from app.indicators.technical import atr, bollinger


def atr_pct(high: Sequence[float], low: Sequence[float], close: Sequence[float], period: int = 14
            ) -> List[Optional[float]]:
    """ATR expressed as a percentage of price (scale-free across FX/OTC pairs)."""
    values = atr(high, low, close, period)
    out: List[Optional[float]] = []
    for i, v in enumerate(values):
        if v is None or not close[i]:
            out.append(None)
        else:
            out.append(v / close[i] * 100.0)
    return out


def normalised_atr(high: Sequence[float], low: Sequence[float], close: Sequence[float],
                   period: int = 14, lookback: int = 100) -> Optional[float]:
    """Current ATR% relative to its own recent median (1.0 = typical)."""
    series = [v for v in atr_pct(high, low, close, period) if v is not None]
    if len(series) < 20:
        return None
    current = series[-1]
    sample = series[-lookback:] if len(series) >= lookback else series
    med = statistics.median(sample)
    if med <= 0:
        return None
    return current / med


def volatility_stability(high: Sequence[float], low: Sequence[float], close: Sequence[float],
                         period: int = 14, lookback: int = 60) -> Optional[float]:
    """0..1 score: 1 = very stable ATR, 0 = wildly unstable.

    Uses the coefficient of variation of the last `lookback` ATR values.
    """
    series = [v for v in atr_pct(high, low, close, period) if v is not None]
    if len(series) < 20:
        return None
    sample = series[-lookback:] if len(series) >= lookback else series
    mean = statistics.fmean(sample)
    if mean <= 0:
        return None
    cv = statistics.pstdev(sample) / mean
    # cv of 0 -> 1.0 ; cv of 1.0 -> ~0.0 (clamped)
    return max(0.0, min(1.0, 1.0 - cv))


def squeeze_state(close: Sequence[float], period: int = 20, deviations: float = 2.0,
                  lookback: int = 120) -> dict:
    """Bollinger width percentile vs its own recent history."""
    _, _, _, width = bollinger(close, period, deviations)
    defined = [w for w in width if w is not None]
    if len(defined) < 30:
        return {"available": False}
    current = defined[-1]
    sample = defined[-lookback:] if len(defined) >= lookback else defined
    below = sum(1 for w in sample if w <= current)
    pct = below / len(sample) * 100.0
    return {
        "available": True,
        "width": current,
        "width_percentile": pct,
        "squeezed": pct <= 20.0,
        "expanded": pct >= 80.0,
    }


def impulse_candle_ratio(high: Sequence[float], low: Sequence[float], close: Sequence[float],
                         open_: Sequence[float], period: int = 14) -> Optional[float]:
    """Latest candle range relative to the recent average range (>1 = impulse)."""
    if len(close) < period + 1:
        return None
    rng = high[-1] - low[-1]
    recent = [high[i] - low[i] for i in range(len(close) - period, len(close) - 1)]
    avg = statistics.fmean(recent) if recent else 0.0
    if avg <= 0:
        return None
    return rng / avg
