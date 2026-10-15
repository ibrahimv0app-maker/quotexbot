"""BT10 — M5_M1_ALIGNMENT. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT10Strategy(BTStrategy):
    strategy_id = 'BT10'
    name = 'M5_M1_ALIGNMENT'
    family = 'continuation'
    reversal = False
    supported_regimes = ('TREND_UP', 'TREND_DOWN', 'EXPANSION')
    defaults = {**BTStrategy.defaults, **{'alignment_body': 0.45}}
    def trigger(self, bt, side):
        p=self.parameters
        prev=self.previous(bt)
        ok=prev is not None and self.aligned(bt,side) and bt.features.get('resume_side')==side and bt.features.get('body_ratio',0)>=p['alignment_body'] and self.pressure(bt,side)>self.pressure(prev,side)
        return ok,.9,'closed M5 agreement plus fresh M1 continuation trigger' if ok else 'no aligned M1 continuation trigger'

