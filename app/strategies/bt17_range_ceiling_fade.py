"""BT17 — RANGE_CEILING_FADE. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT17Strategy(BTStrategy):
    strategy_id = 'BT17'
    name = 'RANGE_CEILING_FADE'
    family = 'range'
    reversal = True
    supported_regimes = ('RANGE',)
    defaults = {**BTStrategy.defaults, **{'ceiling_location': 0.8, 'ceiling_recovery': 5.0}}
    def trigger(self, bt, side):
        p=self.parameters
        loc=bt.features.get('range_location')
        ok=side==-1 and bt.features.get('range_valid',False) and loc is not None and loc>=p['ceiling_location'] and bt.features.get('rejection_side')==-1 and self.rising(bt,-1,p['ceiling_recovery'])
        return ok,.9,'validated range ceiling rejected with bearish recovery' if ok else 'no confirmed range-ceiling fade'

