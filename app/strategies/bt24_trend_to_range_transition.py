"""BT24 — TREND_TO_RANGE_TRANSITION. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT24Strategy(BTStrategy):
    strategy_id = 'BT24'
    name = 'TREND_TO_RANGE_TRANSITION'
    family = 'range'
    reversal = True
    supported_regimes = ('RANGE',)
    defaults = {**BTStrategy.defaults, **{'transition_pressure_drop': 15.0, 'range_transition_shift': 5.0}}
    def trigger(self, bt, side):
        p=self.parameters
        old=[x for x in bt.previous[-5:] if x.BT_REGIME in ('TREND_UP','TREND_DOWN')]
        ok=bool(old) and bt.features.get('range_valid',False) and old[-1].BT_PRESSURE-bt.BT_PRESSURE>=p['transition_pressure_drop'] and bt.features.get('rejection_side')==side and self.rising(bt,side,p['range_transition_shift'])
        return ok,.9,'trend pressure faded into validated range; boundary rejection confirmed' if ok else 'weak trend alone does not establish range transition'

