"""Validated, versioned research defaults. No threshold is a profitability claim."""
from __future__ import annotations
import json,math
from dataclasses import dataclass,field,fields
from pathlib import Path
from app.black_tornado.models import freeze

@dataclass(frozen=True)
class BTConfig:
    lookback: int = 200
    observation_history: int = 8
    robust_period: int = 60
    ema_fast: int = 9
    ema_mid: int = 21
    ema_slow: int = 50
    rsi_fast: int = 7
    rsi_slow: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    stochastic_period: int = 14
    roc_period: int = 3
    ema_slope_period: int = 3
    pressure_period: int = 3
    atr_period: int = 14
    bb_period: int = 20
    bb_deviation: float = 2
    pivot_left: int = 2
    pivot_right: int = 2
    swing_lookback: int = 70
    technical_weights: dict = field(default_factory=lambda:dict(trend=.40,momentum=.30,movement=.20,oscillator=.10))
    behavior_weights: dict = field(default_factory=lambda:dict(structure=.30,pressure=.20,breakout=.20,rejection=.10,exhaustion=.10,htf=.10))
    min_trend_direction: float = 30
    trend_adx: float = 20
    range_adx: float = 23
    squeeze_percentile: float = 20
    expansion_atr_ratio: float = 1.25
    breakout_atr_buffer: float = .08
    retest_atr_tolerance: float = .35
    level_atr_tolerance: float = .65
    range_boundary_atr_tolerance: float = 1.2
    rejection_wick: float = .38
    max_turbulence: float = 70
    chaos_turbulence: float = 80
    chaos_range_atr: float = 4
    reversal_exhaustion: float = 65
    max_extension_atr: float = 3
    max_spike_age: int = 6

    def __post_init__(self):
        if not 120<=self.lookback<=280 or not 3<=self.observation_history<=12:
            raise ValueError('BT lookback/history outside supported causal window')
        if self.robust_period<20 or self.robust_period>self.lookback-50:
            raise ValueError('Invalid robust normalization history')
        if self.macd_slow+self.macd_signal+self.robust_period>self.lookback:
            raise ValueError('Insufficient history for robust MACD normalization')
        for k in ('technical_weights','behavior_weights'):
            weights=getattr(self,k)
            expected={'trend','momentum','movement','oscillator'} if k=='technical_weights' else {'structure','pressure','breakout','rejection','exhaustion','htf'}
            if set(weights)!=expected or any(not math.isfinite(v) or v<0 for v in weights.values()) or abs(sum(weights.values())-1)>1e-8:
                raise ValueError(f'{k} must contain documented families and sum to one')
        for name in ('ema_fast','ema_mid','ema_slow','rsi_fast','rsi_slow','atr_period','bb_period','pivot_left','pivot_right','macd_fast','macd_slow','macd_signal','stochastic_period','roc_period','ema_slope_period','pressure_period'):
            if type(getattr(self,name)) is not int or not 1<=getattr(self,name)<self.lookback//2: raise ValueError(f'Invalid {name}')

        object.__setattr__(self,'technical_weights',freeze(self.technical_weights))
        object.__setattr__(self,'behavior_weights',freeze(self.behavior_weights))

    @classmethod
    def load(cls,path):
        data=json.loads(Path(path).read_text()) if Path(path).is_file() else {}
        known={f.name for f in fields(cls)}
        if set(data)-known: raise ValueError('Unknown BT core settings: '+str(set(data)-known))
        return cls(**data)
