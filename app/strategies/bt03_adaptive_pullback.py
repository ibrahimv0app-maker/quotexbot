"""BT03 — ADAPTIVE_PULLBACK. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT03Strategy(BTStrategy):
    strategy_id = 'BT03'
    name = 'ADAPTIVE_PULLBACK'
    family = 'pullback'
    reversal = False
    supported_regimes = ('TREND_UP', 'TREND_DOWN', 'EXPANSION')
    defaults = {**BTStrategy.defaults, **{'pullback_distance': 1.0, 'recovery': 4.0}}
    def trigger(self, bt, side):
        p=self.parameters
        prev=self.previous(bt)
        near=any(x.features.get('mean_distance_atr',999)<=p['pullback_distance'] for x in bt.previous[-3:])
        ok=prev is not None and near and bt.features.get('mean_rejection_side')==side and bt.features.get('ema_trend_side')==side and self.rising(bt,side,p['recovery'])
        return ok,.95,'adaptive-mean pullback rejected with pressure recovery' if ok else 'no mean pullback and recovery'

