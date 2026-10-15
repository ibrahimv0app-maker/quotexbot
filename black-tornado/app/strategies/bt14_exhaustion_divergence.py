"""BT14 — EXHAUSTION_DIVERGENCE. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT14Strategy(BTStrategy):
    strategy_id = 'BT14'
    name = 'EXHAUSTION_DIVERGENCE'
    family = 'reversal'
    reversal = True
    supported_regimes = ('RANGE', 'REVERSAL_RISK', 'EXPANSION')
    defaults = {**BTStrategy.defaults, **{'divergence_exhaustion': 50.0, 'divergence_shift': 8.0}}
    def trigger(self, bt, side):
        p=self.parameters
        pivots=bt.features.get('divergence_pivots',[])
        confirmed=len(pivots)==2 and all(x['confirmed_ts']<=bt.closed_through for x in pivots)
        ok=confirmed and bt.features.get('divergence_side')==side and bt.BT_EXHAUSTION>=p['divergence_exhaustion'] and side*bt.features.get('body_signed',0)>0 and self.rising(bt,side,p['divergence_shift'])
        return ok,.95,'confirmed pivots diverge from historical BT pressure; reversal confirmed' if ok else 'confirmed-pivot divergence/reversal absent'

