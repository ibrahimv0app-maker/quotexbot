"""BT12 — FAILED_BREAKOUT_TRAP. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT12Strategy(BTStrategy):
    strategy_id = 'BT12'
    name = 'FAILED_BREAKOUT_TRAP'
    family = 'reclaim'
    reversal = True
    supported_regimes = ('RANGE', 'REVERSAL_RISK', 'EXPANSION')
    defaults = {**BTStrategy.defaults, **{'trap_shift': 12.0}}
    def trigger(self, bt, side):
        p=self.parameters
        prior=bt.features.get('prior_breakout')
        ok=bool(prior and prior['breakout']==-side and bt.features.get('failed_breakout_side')==side and self.rising(bt,side,p['trap_shift']))
        return ok,.95,'prior breakout failed and BT shifted to opposite side' if ok else 'known breakout failure/shift absent'

