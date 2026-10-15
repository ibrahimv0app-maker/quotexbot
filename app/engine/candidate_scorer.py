"""BT ranking, no vote count: 20 direction + 25 trigger + 15 behavior + 10 regime
+ 15 turbulence + 5 HTF + 10 sufficiently validated held-out performance.
Missing components are disclosed and dropped, never assigned imaginary evidence.
"""
from dataclasses import dataclass,field
import math

@dataclass
class ScoredCandidate:
    candidate: object
    score: float
    components: dict = field(default_factory=dict)
    available_weight: float = 100
    performance_sample: int | None = None
    performance_note: str = ''
    def to_dict(self):
        return dict(symbol=self.candidate.symbol,strategy=self.candidate.strategy,direction=self.candidate.direction,
            score=round(self.score,2),max_score=100,available_weight=self.available_weight,
            components=self.components,reasons=self.candidate.reasons,filters_passed=self.candidate.filters_passed,
            details=self.candidate.details,performance_sample=self.performance_sample,performance_note=self.performance_note)

class CandidateScorer:
    def __init__(self,settings): self.settings=settings
    def score(self,ctx,cand,performance=None):
        bt=cand.details.get('bt',{})
        if not bt.get('BT_DATA_OK'): return ScoredCandidate(cand,0,{},0,performance_note='BT invalid')
        side=1 if cand.direction=='CALL' else -1
        f=bt['features'];s=self.settings
        raw=dict(direction=max(0,side*bt['BT_DIRECTION'])/100,
            trigger=cand.details['trigger_quality'],
            behavior=max(0,side*bt['BT_BEHAVIOR_DIRECTION'])/100,
            regime=1.0 if bt['BT_REGIME'] in ('TREND_UP','TREND_DOWN','RANGE','REVERSAL_RISK') else .8,
            turbulence=max(0,1-bt['BT_TURBULENCE']/100),
            htf=None,performance=None)
        if 'htf' not in bt.get('missing',[]):
            alignment=bt['BT_HTF_ALIGNMENT']
            raw['htf']=1. if alignment==('BULLISH' if side==1 else 'BEARISH') else (.5 if alignment=='NEUTRAL' else (.25 if cand.details.get('reversal') else 0.))
        sample=None;notes=[]
        p=performance
        if p and p.get('source')=='tick_replay' and p.get('split')=='test' and p.get('engine_version')=='BLACK_TORNADO_1.0' and p.get('config_hash')==cand.details.get('config_hash') and p.get('strategy')==cand.strategy and p.get('symbol')==cand.symbol and p.get('test_end_ts',float('inf'))<bt['decision_ts']:
            n=p.get('wins',0)+p.get('losses',0)
            if n>=s.MIN_PERFORMANCE_SAMPLE:
                sample=n;rate=(p['wins']+1)/(n+2)
                # Conservative beta-binomial smoothing, no two-win promotion.
                raw['performance']=max(0,min(1,(rate-.35)/.45))
        weights=dict(direction=s.SCORE_DIRECTION,trigger=s.SCORE_TRIGGER,behavior=s.SCORE_BEHAVIOR,
            regime=s.SCORE_REGIME,turbulence=s.SCORE_TURBULENCE,htf=s.SCORE_HTF,performance=s.SCORE_PERFORMANCE)
        used=sum(weights[k] for k,v in raw.items() if v is not None)
        for k,v in raw.items():
            if v is None: notes.append(k+' unavailable/dropped')
        parts={k:round(weights[k]*v,4) for k,v in raw.items() if v is not None}
        score=100*sum(parts.values())/used if used else 0
        return ScoredCandidate(cand,score,parts,used,sample,'; '.join(notes))
