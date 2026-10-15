"""BT11 — SWEEP_AND_RECLAIM. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT11Strategy(BTStrategy):
    strategy_id = 'BT11'
    name = 'SWEEP_AND_RECLAIM'
    family = 'reclaim'
    reversal = True
    supported_regimes = ('RANGE', 'REVERSAL_RISK', 'EXPANSION', 'TREND_UP', 'TREND_DOWN')
    defaults = {**BTStrategy.defaults, **{'reclaim_pressure': 25.0}}
    def trigger(self, bt, side):
        p=self.parameters
        ok=bt.features.get('sweep_side')==side and self.pressure(bt,side)>=p['reclaim_pressure'] and bt.features.get('rejection_side')==side
        return ok,.95,'price-only sweep proxy reclaimed known level with rejection' if ok else 'no structural sweep/reclaim confirmation'

