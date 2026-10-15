"""BT16 — RANGE_FLOOR_BOUNCE. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT16Strategy(BTStrategy):
    strategy_id = 'BT16'
    name = 'RANGE_FLOOR_BOUNCE'
    family = 'range'
    reversal = True
    supported_regimes = ('RANGE',)
    defaults = {**BTStrategy.defaults, **{'floor_location': 0.2, 'floor_recovery': 5.0}}
    def trigger(self, bt, side):
        p=self.parameters
        loc=bt.features.get('range_location')
        ok=side==1 and bt.features.get('range_valid',False) and loc is not None and loc<=p['floor_location'] and bt.features.get('rejection_side')==1 and self.rising(bt,1,p['floor_recovery'])
        return ok,.9,'validated range floor rejected with bullish recovery' if ok else 'no confirmed range-floor bounce'

