"""BT05 — STORM_ACCELERATION. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT05Strategy(BTStrategy):
    strategy_id = 'BT05'
    name = 'STORM_ACCELERATION'
    family = 'continuation'
    reversal = False
    supported_regimes = ('TREND_UP', 'TREND_DOWN', 'EXPANSION')
    defaults = {**BTStrategy.defaults, **{'direction_acceleration': 12.0}}
    def trigger(self, bt, side):
        p=self.parameters
        seq=list(bt.previous[-2:])+[bt]
        ok=len(seq)==3 and all(side*seq[i].BT_DIRECTION>side*seq[i-1].BT_DIRECTION for i in (1,2)) and side*(seq[-1].BT_DIRECTION-seq[0].BT_DIRECTION)>=p['direction_acceleration'] and all(self.pressure(seq[i],side)>self.pressure(seq[i-1],side) for i in (1,2))
        return ok,.95,'three closed observations show accelerating direction and pressure' if ok else 'acceleration sequence absent'

