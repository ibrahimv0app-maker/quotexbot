"""BT22 — SPIKE_EXHAUSTION_REVERSAL. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT22Strategy(BTStrategy):
    strategy_id = 'BT22'
    name = 'SPIKE_EXHAUSTION_REVERSAL'
    family = 'reversal'
    reversal = True
    supported_regimes = ('REVERSAL_RISK', 'RANGE', 'EXPANSION')
    defaults = {**BTStrategy.defaults, **{'spike_reversal_age': 5.0, 'spike_exhaustion': 65.0, 'spike_shift': 8.0}}
    def trigger(self, bt, side):
        p=self.parameters
        age=bt.features.get('last_spike_age')
        evidence=bt.features.get('failed_breakout_side')==side or bt.features.get('sweep_side')==side or bt.features.get('rejection_side')==side
        ok=age is not None and 1<=age<=p['spike_reversal_age'] and evidence and bt.BT_EXHAUSTION>=p['spike_exhaustion'] and self.rising(bt,side,p['spike_shift'])
        return ok,.95,'post-spike failed extension/rejection plus reversal confirmation' if ok else 'spike alone is not reversal evidence'

