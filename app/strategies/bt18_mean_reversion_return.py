"""BT18 — MEAN_REVERSION_RETURN. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT18Strategy(BTStrategy):
    strategy_id = 'BT18'
    name = 'MEAN_REVERSION_RETURN'
    family = 'range'
    reversal = True
    supported_regimes = ('RANGE',)
    defaults = {**BTStrategy.defaults, **{'return_displacement': 1.5, 'return_shift': 5.0}}
    def trigger(self, bt, side):
        p=self.parameters
        prev=self.previous(bt)
        loc=bt.features.get('range_location')
        ok=prev is not None and bt.features.get('range_valid',False) and loc is not None and 0<=loc<=1 and side*prev.features.get('deviation_atr',0)<=-p['return_displacement'] and abs(bt.features.get('deviation_atr',0))<abs(prev.features.get('deviation_atr',0)) and self.rising(bt,side,p['return_shift'])
        return ok,.9,'extended range price re-entered toward adaptive mean' if ok else 'mean return/re-entry absent'

