"""BT15 — OVEREXTENSION_SNAPBACK. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT15Strategy(BTStrategy):
    strategy_id = 'BT15'
    name = 'OVEREXTENSION_SNAPBACK'
    family = 'reversal'
    reversal = True
    supported_regimes = ('RANGE', 'REVERSAL_RISK')
    defaults = {**BTStrategy.defaults, **{'snapback_displacement': 2.0, 'snapback_exhaustion': 65.0, 'snapback_shift': 5.0}}
    def trigger(self, bt, side):
        p=self.parameters
        ok=bt.features.get('range_valid',False) and side*bt.features.get('deviation_atr',0)<=-p['snapback_displacement'] and bt.BT_EXHAUSTION>=p['snapback_exhaustion'] and bt.features.get('resume_side')==side and self.rising(bt,side,p['snapback_shift'])
        return ok,.95,'extended range move exhausted with confirmed return pressure' if ok else 'no safe overextension snapback'

