"""Technical indicators - pure Python, no look-ahead, no pandas in the hot path.

Every function takes an ordered list of values (oldest -> newest) and returns a
list of the same length where element i only uses data up to and including i.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple


def sma(values: Sequence[float], period: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    running = sum(values[:period])
    out[period - 1] = running / period
    for i in range(period, len(values)):
        running += values[i] - values[i - period]
        out[i] = running / period
    return out


def ema(values: Sequence[float], period: int) -> List[Optional[float]]:
    """Standard EMA seeded with the first `period` SMA."""
    out: List[Optional[float]] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    k = 2.0 / (period + 1)
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(values: Sequence[float], period: int = 14) -> List[Optional[float]]:
    """Wilder's RSI."""
    out: List[Optional[float]] = [None] * len(values)
    if len(values) <= period:
        return out
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        d = values[i] - values[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    avg_gain = gains / period
    avg_loss = losses / period
    out[period] = (50.0 if avg_gain == 0 else 100.0) if avg_loss == 0 else 100.0 - 100.0 / (1 + avg_gain / avg_loss)
    for i in range(period + 1, len(values)):
        d = values[i] - values[i - 1]
        gain = max(d, 0.0)
        loss = max(-d, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = (50.0 if avg_gain == 0 else 100.0) if avg_loss == 0 else 100.0 - 100.0 / (1 + avg_gain / avg_loss)
    return out


def macd(values: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9
         ) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    ef = ema(values, fast)
    es = ema(values, slow)
    line: List[Optional[float]] = [None] * len(values)
    for i in range(len(values)):
        if ef[i] is not None and es[i] is not None:
            line[i] = ef[i] - es[i]
    # signal EMA over the defined part of the line
    sig: List[Optional[float]] = [None] * len(values)
    hist: List[Optional[float]] = [None] * len(values)
    defined = [v for v in line if v is not None]
    if len(defined) >= signal:
        sig_defined = ema(defined, signal)
        idx = [i for i, v in enumerate(line) if v is not None]
        for j, i in enumerate(idx):
            sig[i] = sig_defined[j]
            if sig[i] is not None:
                hist[i] = line[i] - sig[i]
    return line, sig, hist


def true_range(high: Sequence[float], low: Sequence[float], close: Sequence[float]) -> List[float]:
    out: List[float] = []
    for i in range(len(close)):
        if i == 0:
            out.append(high[0] - low[0])
        else:
            pc = close[i - 1]
            out.append(max(high[i] - low[i], abs(high[i] - pc), abs(low[i] - pc)))
    return out


def atr(high: Sequence[float], low: Sequence[float], close: Sequence[float], period: int = 14
        ) -> List[Optional[float]]:
    tr = true_range(high, low, close)
    out: List[Optional[float]] = [None] * len(tr)
    if len(tr) < period:
        return out
    prev = sum(tr[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(tr)):
        prev = (prev * (period - 1) + tr[i]) / period
        out[i] = prev
    return out


def bollinger(close: Sequence[float], period: int = 20, deviations: float = 2.0
              ) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    mid = sma(close, period)
    upper = [None] * len(close)
    lower = [None] * len(close)
    width = [None] * len(close)
    if len(close)<period: return mid,upper,lower,width
    # Centering avoids catastrophic cancellation for small FX variances.
    anchor = close[0]
    vals = [x-anchor for x in close]
    total = sum(vals[:period]); sq = sum(x*x for x in vals[:period])
    for i in range(period-1,len(close)):
        if i >= period:
            new,old = vals[i],vals[i-period]
            total += new-old; sq += new*new-old*old
        var = max(0.0,sq/period-(total/period)**2)
        sd = math.sqrt(var)
        upper[i],lower[i] = mid[i]+deviations*sd,mid[i]-deviations*sd
        width[i] = 2*deviations*sd/mid[i] if mid[i] else None
    return mid,upper,lower,width


def adx(high: Sequence[float], low: Sequence[float], close: Sequence[float], period: int = 14
        ) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """Returns (adx, +DI, -DI)."""
    n = len(close)
    out,pdi,mdi = [None]*n,[None]*n,[None]*n
    if n < 2*period: return out,pdi,mdi
    tr = true_range(high,low,close)
    pdm,mdm = [0.0]*n,[0.0]*n
    for i in range(1,n):
        up,dn = high[i]-high[i-1],low[i-1]-low[i]
        pdm[i] = up if up>dn and up>0 else 0.0
        mdm[i] = dn if dn>up and dn>0 else 0.0
    st,sp,sm = sum(tr[1:period+1]),sum(pdm[1:period+1]),sum(mdm[1:period+1])
    dx = [None]*n
    for i in range(period,n):
        if i>period:
            st = st-st/period+tr[i]
            sp = sp-sp/period+pdm[i]
            sm = sm-sm/period+mdm[i]
        pdi[i],mdi[i] = (100*sp/st,100*sm/st) if st>0 else (0.0,0.0)
        denom = pdi[i]+mdi[i]
        dx[i] = 100*abs(pdi[i]-mdi[i])/denom if denom else 0.0
    first = 2*period-1
    out[first] = sum(dx[period:first+1])/period
    for i in range(first+1,n): out[i] = (out[i-1]*(period-1)+dx[i])/period
    return out,pdi,mdi


def swing_points(high: Sequence[float], low: Sequence[float], left: int = 2, right: int = 2
                 ) -> Tuple[List[Optional[float]], List[Optional[float]]]:
    """Fractal swing highs/lows. A pivot at i is only known at i+right (no repaint)."""
    highs: List[Optional[float]] = [None] * len(high)
    lows: List[Optional[float]] = [None] * len(low)
    for i in range(left, len(high) - right):
        window_h = high[i - left:i + right + 1]
        if high[i] == max(window_h) and window_h.count(high[i]) == 1:
            highs[i] = high[i]
        window_l = low[i - left:i + right + 1]
        if low[i] == min(window_l) and window_l.count(low[i]) == 1:
            lows[i] = low[i]
    return highs, lows


def slope(values: Sequence[Optional[float]], lookback: int) -> Optional[float]:
    """Relative slope over `lookback` bars (percentage), using the last defined values."""
    if len(values) <= lookback or values[-1] is None or values[-1-lookback] in (None, 0):
        return None
    return (values[-1] / values[-1-lookback] - 1) * 100.0 / lookback


def crossed_above(fast: Sequence[Optional[float]], slow: Sequence[Optional[float]], index: int = -1) -> bool:
    i = index if index >= 0 else len(fast) - 1
    if i < 1 or i >= len(fast) or i >= len(slow):
        return False
    f0, f1 = fast[i], fast[i - 1]
    s0, s1 = slow[i], slow[i - 1]
    if None in (f0, f1, s0, s1):
        return False
    return f1 <= s1 and f0 > s0


def crossed_below(fast: Sequence[Optional[float]], slow: Sequence[Optional[float]], index: int = -1) -> bool:
    i = index if index >= 1 else len(fast) - 1
    if i < 1 or i >= len(fast) or i >= len(slow):
        return False
    f0, f1 = fast[i], fast[i - 1]
    s0, s1 = slow[i], slow[i - 1]
    if None in (f0, f1, s0, s1):
        return False
    return f1 >= s1 and f0 < s0


# Closed-candle indicator inputs are immutable for an entire minute. Bounded
# memoisation eliminates duplicate work across strategies and the 1Hz scanner.
from functools import lru_cache, wraps

def _memoize_series(fn):
    cached = lru_cache(maxsize=256)(fn)
    @wraps(fn)
    def wrapped(*args, **kwargs):
        args = tuple(tuple(x) if isinstance(x,list) else x for x in args)
        return cached(*args, **kwargs)
    return wrapped

for _name in ('sma','ema','rsi','macd','atr','bollinger','adx'):
    globals()[_name] = _memoize_series(globals()[_name])
