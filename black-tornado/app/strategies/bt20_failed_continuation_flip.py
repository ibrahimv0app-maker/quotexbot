"""BT20 — FAILED_CONTINUATION_FLIP. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT20Strategy(BTStrategy):
    strategy_id = 'BT20'
    name = 'FAILED_CONTINUATION_FLIP'
    family = 'reversal'
    reversal = True
    supported_regimes = ('REVERSAL_RISK', 'EXPANSION', 'RANGE')
    defaults = {**BTStrategy.defaults, **{'prior_continuation': 30.0, 'flip_pressure': 30.0, 'flip_shift': 15.0}}
    def trigger(self, bt, side):
        p=self.parameters
        prev=self.previous(bt)
        prior=any((-side*x.BT_DIRECTION)>=p['prior_continuation'] and x.BT_REGIME in ('TREND_UP','TREND_DOWN','EXPANSION') for x in bt.previous[-3:])
        structural=bt.features.get('failed_breakout_side')==side or bt.features.get('breakout_side')==side
        ok=prev is not None and prior and structural and self.pressure(bt,side)>=p['flip_pressure'] and self.rising(bt,side,p['flip_shift'])
        return ok,.95,'continuation pressure failed; opposite structural confirmation' if ok else 'continuation failure/flip not confirmed'

