"""BT19 — DOUBLE_SWEEP_TRAP. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT19Strategy(BTStrategy):
    strategy_id = 'BT19'
    name = 'DOUBLE_SWEEP_TRAP'
    family = 'reclaim'
    reversal = True
    supported_regimes = ('RANGE', 'REVERSAL_RISK', 'EXPANSION')
    defaults = {**BTStrategy.defaults, **{'double_pressure': 30.0, 'double_shift': 5.0}}
    def trigger(self, bt, side):
        p=self.parameters
        ok=bt.features.get('double_sweep_side')==side and bt.features.get('sweep_side')==side and self.pressure(bt,side)>=p['double_pressure'] and self.rising(bt,side,p['double_shift'])
        return ok,.95,'two failed penetrations at same boundary; opposite reclaim proxy' if ok else 'double sweep/reclaim not confirmed'

