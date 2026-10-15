"""BT07 — BREAKOUT_RETEST. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT07Strategy(BTStrategy):
    strategy_id = 'BT07'
    name = 'BREAKOUT_RETEST'
    family = 'pullback'
    reversal = False
    supported_regimes = ('TREND_UP', 'TREND_DOWN', 'EXPANSION')
    defaults = {**BTStrategy.defaults, **{'max_retest_age': 5.0, 'retest_recovery': 4.0}}
    def trigger(self, bt, side):
        p=self.parameters
        prior=bt.features.get('prior_breakout')
        ok=bool(prior and 1<=prior['age']<=p['max_retest_age'] and prior['breakout']==side and bt.features.get('retest_side')==side and self.rising(bt,side,p['retest_recovery']))
        return ok,.95,'known breakout retested, accepted and pressure renewed' if ok else 'retest/acceptance not confirmed'

