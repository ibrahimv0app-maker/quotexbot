from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
import copy

REGIMES = ('TREND_UP','TREND_DOWN','RANGE','SQUEEZE','EXPANSION','REVERSAL_RISK','CHAOS','UNKNOWN')

class FrozenDict(dict):
    """Read-only JSON-compatible mapping; snapshots deepcopy to plain dicts."""
    def _deny(self,*args,**kwargs): raise TypeError('BT feature snapshots are immutable')
    __setitem__=__delitem__=clear=pop=popitem=setdefault=update=__ior__=_deny
    def __deepcopy__(self,memo): return {k:copy.deepcopy(v,memo) for k,v in self.items()}

def freeze(value):
    if isinstance(value,dict): return FrozenDict({k:freeze(v) for k,v in value.items()})
    if isinstance(value,(list,tuple)): return tuple(freeze(v) for v in value)
    return value

@dataclass(frozen=True)
class BTFrame:
    symbol: str
    decision_ts: float
    closed_through: int
    BT_DIRECTION: float = 0
    BT_TECHNICAL_DIRECTION: float = 0
    BT_BEHAVIOR_DIRECTION: float = 0
    BT_CONFIDENCE: float = 0
    BT_PRESSURE: float = 0
    BT_TURBULENCE: float = 100
    BT_EXHAUSTION: float = 0
    BT_REGIME: str = 'UNKNOWN'
    BT_STRUCTURE: str = 'UNCONFIRMED'
    BT_SWEEP_RECLAIM: str = 'NONE'
    BT_BREAKOUT: str = 'NONE'
    BT_HTF_ALIGNMENT: str = 'NEUTRAL'
    BT_DATA_OK: bool = False
    features: dict[str, Any] = field(default_factory=dict)
    components: dict[str, Any] = field(default_factory=dict)
    missing: tuple[str,...] = ()
    previous: tuple['BTFrame',...] = field(default=(),repr=False,compare=False)

    def __post_init__(self):
        object.__setattr__(self,'features',freeze(self.features))
        object.__setattr__(self,'components',freeze(self.components))

    def snapshot(self, include_history=True):
        data = {k:copy.deepcopy(v) for k,v in vars(self).items() if k!='previous'}
        if include_history:
            data['previous_outputs'] = [{k:getattr(p,k) for k in ('closed_through','BT_DIRECTION','BT_PRESSURE','BT_CONFIDENCE','BT_TURBULENCE','BT_EXHAUSTION','BT_REGIME')} for p in self.previous]
        data['engine_version'] = 'BLACK_TORNADO_1.0'
        data['confidence_is_probability'] = False
        data['sweep_is_price_proxy'] = True
        return data

    @property
    def BT_FEATURE_SNAPSHOT(self): return self.snapshot()
