"""BT13 — STRUCTURAL_WICK_REJECTION. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT13Strategy(BTStrategy):
    strategy_id = 'BT13'
    name = 'STRUCTURAL_WICK_REJECTION'
    family = 'reversal'
    reversal = True
    supported_regimes = ('RANGE', 'REVERSAL_RISK', 'EXPANSION')
    defaults = {**BTStrategy.defaults, **{'structural_wick': 0.4, 'rejection_pressure': 25.0}}
    def trigger(self, bt, side):
        p=self.parameters
        wick=bt.features.get('lower_wick' if side==1 else 'upper_wick',0)
        ok=bt.features.get('rejection_side')==side and wick>=p['structural_wick'] and self.pressure(bt,side)>=p['rejection_pressure']
        return ok,.9,'confirmed structure rejected with opposing wick/body pressure' if ok else 'no meaningful structural rejection'

