"""BT01 — TORNADO_IGNITION. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT01Strategy(BTStrategy):
    strategy_id = 'BT01'
    name = 'TORNADO_IGNITION'
    family = 'breakout'
    reversal = False
    supported_regimes = ('TREND_UP', 'TREND_DOWN', 'EXPANSION')
    defaults = {**BTStrategy.defaults, **{'ignition_direction': 35.0, 'ignition_pressure': 40.0}}
    def trigger(self, bt, side):
        p=self.parameters
        transition=any(p.BT_REGIME in ('RANGE','SQUEEZE') for p in bt.previous[-3:])
        ok=transition and bt.features.get('breakout_side')==side and side*bt.BT_DIRECTION>=p['ignition_direction'] and bt.BT_PRESSURE>=p['ignition_pressure']
        return ok,.95,'fresh breakout from range/squeeze' if ok else 'no confirmed ignition transition'

