"""BT08 — SQUEEZE_RELEASE. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT08Strategy(BTStrategy):
    strategy_id = 'BT08'
    name = 'SQUEEZE_RELEASE'
    family = 'breakout'
    reversal = False
    supported_regimes = ('EXPANSION', 'TREND_UP', 'TREND_DOWN')
    defaults = {**BTStrategy.defaults, **{'release_pressure': 45.0, 'release_range': 1.0}}
    def trigger(self, bt, side):
        p=self.parameters
        compressed=any(x.BT_REGIME=='SQUEEZE' or x.features.get('compression') for x in bt.previous[-3:])
        ok=compressed and bt.features.get('breakout_side')==side and bt.BT_PRESSURE>=p['release_pressure'] and bt.features.get('range_atr',0)>=p['release_range']
        return ok,.95,'compression released through structure with directional pressure' if ok else 'no confirmed squeeze release'

