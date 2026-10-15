"""Regime and quality filters applied to every candidate before ranking.

Each filter returns a (passed, reason) pair. A candidate must survive ALL
mandatory filters to become eligible.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from app.config import Settings
from app.strategies.base import Candidate, MarketContext



@dataclass
class FilterOutcome:
    passed: bool
    filters_passed: List[str] = field(default_factory=list)
    rejection: str = ""
    details: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"passed": self.passed, "filters_passed": self.filters_passed,
                "rejection": self.rejection, "details": self.details}


class RegimeFilter:
    def __init__(self, settings: Settings):
        self.settings = settings

    # ------------------------------------------------------------------ data
    def data_quality(self, ctx: MarketContext) -> Tuple[bool, str, Dict]:
        d: Dict = {}
        s = self.settings
        if len(ctx.candles) < s.MIN_CLOSED_CANDLES:
            return False, f"insufficient history ({len(ctx.candles)}/{s.MIN_CLOSED_CANDLES})", d
        d["candles"] = len(ctx.candles)
        if ctx.data_age > s.DATA_STALE_SECONDS:
            return False, f"stale data ({ctx.data_age:.1f}s > {s.DATA_STALE_SECONDS}s)", d
        d["data_age"] = round(ctx.data_age, 2)
        last = ctx.candles[-1]
        if last.time + 60 > ctx.now:
            return False, "last candle not closed", d
        # monotonic timestamps
        times = [c.time for c in ctx.candles[-50:]]
        if any(times[i] <= times[i - 1] for i in range(1, len(times))):
            return False, "non-monotonic candle timestamps", d
        if any(times[i]-times[i-1] != 60 for i in range(1, len(times))):
            return False, "missing candle in recent history", d
        if ctx.now - last.close_time > 65:
            return False, "stale closed-candle history", d
        if ctx.data_age < -self.settings.MAX_CLOCK_SKEW_SECONDS:
            return False, "feed clock ahead", d
        if ctx.last_price is None or ctx.last_price <= 0:
            return False, "no live price", d
        return True, "", d

    # ------------------------------------------------------------------ volatility
    def volatility(self, ctx: MarketContext) -> Tuple[bool, str, Dict]:
        d: Dict = {}
        s = self.settings
        if ctx.atr_pct is None:
            return False, "ATR unavailable", d
        d["atr_pct"] = round(ctx.atr_pct, 5)
        if ctx.atr_pct < s.MIN_ATR_PCT:
            return False, f"ATR too low ({ctx.atr_pct:.5f}%) - market inactive", d
        if ctx.atr_pct > s.MAX_ATR_PCT:
            return False, f"ATR too high ({ctx.atr_pct:.5f}%) - unstable regime", d
        if ctx.atr_norm is not None:
            d["atr_norm"] = round(ctx.atr_norm, 2)
            if ctx.atr_norm > s.MAX_ATR_NORMALIZED:
                return False, f"volatility spike (ATR x{ctx.atr_norm:.1f})", d
            if ctx.atr_norm < s.MIN_ATR_NORMALIZED:
                return False, f"volatility compressed (ATR x{ctx.atr_norm:.2f})", d
        # reject an oversized latest candle
        if ctx.candle_quality and ctx.candle_quality.range_atr > 4.0:
            return False, "oversized candle", d
        if ctx.vol_stability is not None:
            d["vol_stability"] = round(ctx.vol_stability, 3)
            if ctx.vol_stability < s.MIN_VOL_STABILITY:
                return False, "unstable volatility", d
        return True, "", d

    def apply(self,ctx,cand):
        ok,reason,details=self.data_quality(ctx)
        if not ok: return FilterOutcome(False,[],"data: "+reason,details)
        bt=cand.details.get('bt')
        if not bt or not bt.get('BT_DATA_OK'): return FilterOutcome(False,[],"BT data gate false")
        if bt['BT_REGIME'] in ('CHAOS','UNKNOWN','SQUEEZE'): return FilterOutcome(False,[],"BT regime unsuitable")
        if bt['BT_TURBULENCE']>self.settings.BT_MAX_TURBULENCE: return FilterOutcome(False,[],"BT turbulence excessive")
        if bt['BT_CONFIDENCE']<self.settings.BT_MIN_CONFIDENCE: return FilterOutcome(False,[],"BT consistency below gate")
        side=1 if cand.direction=='CALL' else -1
        if side*bt['BT_DIRECTION']<self.settings.BT_MIN_DIRECTION: return FilterOutcome(False,[],"BT direction not confirmed")
        ok,reason,vol=self.volatility(ctx)
        if not ok: return FilterOutcome(False,[],"volatility: "+reason,vol)
        return FilterOutcome(True,['fresh data','BT direction/trigger','regime compatible','turbulence acceptable'],details={'data':details,'volatility':vol})
