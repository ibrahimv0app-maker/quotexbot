"""Shared contracts; modules interpret BT outputs, never import raw indicators."""
from __future__ import annotations
from dataclasses import dataclass
import math,json,hashlib
from app.strategies.base import Candidate

@dataclass(frozen=True)
class StrategyAssessment:
    candidate: Candidate | None
    rejection: str = ''

class BTStrategy:
    strategy_id = ''
    name = ''
    family = ''
    reversal = False
    supported_regimes = ()
    sides = (1,-1)
    defaults = dict(min_direction=18.,min_pressure=25.,max_turbulence=70.,max_extension=3.,min_confidence=50.)
    def __init__(self,engine,settings=None):
        self.engine=engine
        self.parameters={**self.defaults,**(settings or {})}
        if set(self.parameters)-set(self.defaults): raise ValueError('Unknown strategy threshold')
        if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in self.parameters.values()): raise ValueError('Thresholds must be numeric')
    @property
    def identifier(self): return f'{self.strategy_id} — {self.name}'
    def evaluate(self,ctx): return self.assess(self.engine.analyze(ctx)).candidate
    def assess(self,bt):
        p=self.parameters
        if not bt.BT_DATA_OK: return StrategyAssessment(None,'BT_DATA_OK false')
        if bt.BT_REGIME not in self.supported_regimes: return StrategyAssessment(None,'unsupported regime')
        if bt.BT_TURBULENCE>p['max_turbulence']: return StrategyAssessment(None,'excessive turbulence')
        if bt.BT_CONFIDENCE<p['min_confidence']: return StrategyAssessment(None,'low internal consistency')
        reasons=[];found=[]
        for side in self.sides:
            if side*bt.BT_DIRECTION<p['min_direction']: reasons.append('direction not confirmed');continue
            if bt.BT_PRESSURE<p['min_pressure']: reasons.append('weak directional pressure');continue
            if not self.reversal and bt.features.get('mean_distance_atr',999)>p['max_extension']:
                reasons.append('overextended continuation');continue
            if self.reversal and bt.previous and side*bt.previous[-1].BT_DIRECTION < -60 and bt.BT_EXHAUSTION<60:
                reasons.append('unbroken powerful opposing trend');continue
            ok,quality,reason=self.trigger(bt,side)
            if not ok: reasons.append(reason);continue
            # If a fresh live observation invalidates the structural premise, skip.
            live=bt.features.get('live_beyond_level')
            if live is not None and self.family in ('breakout','pullback') and bt.features.get('event_level') is not None and side*live<-.15:
                reasons.append('live price lost setup level');continue
            strength=min(1.,max(0.,.55*quality+.25*abs(bt.BT_DIRECTION)/100+.2*bt.BT_PRESSURE/100))
            snapshot=bt.snapshot()
            found.append(Candidate(bt.symbol,self.strategy_id,'CALL' if side==1 else 'PUT',strength,
                [reason],['BT data gate','regime compatible','turbulence acceptable'],
                dict(trigger_quality=quality,trigger_parameters=dict(self.parameters),engine_version='BLACK_TORNADO_1.0',config_hash=hashlib.sha256(json.dumps([bt.components.get('config_hash'),self.parameters],sort_keys=True).encode()).hexdigest(),strategy_id=self.strategy_id,strategy_name=self.name,setup_family=self.family,
                     reversal=self.reversal,bt=snapshot,trend_confirmed=not self.reversal and side*bt.BT_DIRECTION>=30 and bt.BT_REGIME in ('TREND_UP','TREND_DOWN','EXPANSION'),
                     volatility='Stable' if bt.BT_TURBULENCE<40 and .65<=bt.features.get('atr_norm',0)<=1.5 else ('Expanding' if bt.BT_REGIME=='EXPANSION' else 'Suitable'))))
        if len(found)>1: return StrategyAssessment(None,'opposite triggers unresolved')
        return StrategyAssessment(found[0] if found else None,'' if found else '; '.join(sorted(set(reasons))))
    def closed_setups(self,bt):
        """Research counts ONLY: never creates an eligible Candidate or passes a
        live-data gate. Missing entry/decision ticks remain explicitly missing."""
        p=self.parameters
        if not bt.features.get('research_closed_only') or not bt.features.get('closed_data_valid'): return ()
        if bt.BT_REGIME not in self.supported_regimes or bt.BT_TURBULENCE>p['max_turbulence'] or bt.BT_CONFIDENCE<p['min_confidence']: return ()
        out=[]
        for side in self.sides:
            if side*bt.BT_DIRECTION<p['min_direction'] or bt.BT_PRESSURE<p['min_pressure']: continue
            if not self.reversal and bt.features.get('mean_distance_atr',999)>p['max_extension']: continue
            ok,_,_=self.trigger(bt,side)
            if ok: out.append('CALL' if side==1 else 'PUT')
        return tuple(out)

    def trigger(self,bt,side): raise NotImplementedError
    def previous(self,bt,n=1): return bt.previous[-n] if len(bt.previous)>=n else None
    def trend(self,bt,side): return bt.BT_REGIME==('TREND_UP' if side==1 else 'TREND_DOWN')
    def aligned(self,bt,side): return bt.BT_HTF_ALIGNMENT==('BULLISH' if side==1 else 'BEARISH')
    def pressure(self,bt,side): return side*bt.features.get('pressure_signed',0)
    def rising(self,bt,side,minimum=5):
        prev=self.previous(bt)
        return prev is not None and side*(bt.BT_DIRECTION-prev.BT_DIRECTION)>=minimum
