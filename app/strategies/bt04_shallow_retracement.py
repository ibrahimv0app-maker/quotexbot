"""BT04 — SHALLOW_RETRACEMENT. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT04Strategy(BTStrategy):
    strategy_id = 'BT04'
    name = 'SHALLOW_RETRACEMENT'
    family = 'continuation'
    reversal = False
    supported_regimes = ('TREND_UP', 'TREND_DOWN')
    defaults = {**BTStrategy.defaults, **{'pressure_recovery': 5.0}}
    def trigger(self, bt, side):
        p=self.parameters
        prev=self.previous(bt)
        ok=prev is not None and bt.features.get('shallow_retracement_side')==side and bt.features.get('structure_held_side')==side and self.pressure(bt,side)>self.pressure(prev,side)+p['pressure_recovery']
        return ok,.9,'shallow counter-move held structure and resumed' if ok else 'shallow retracement not confirmed'

