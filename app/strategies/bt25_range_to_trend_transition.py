"""BT25 — RANGE_TO_TREND_TRANSITION. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT25Strategy(BTStrategy):
    strategy_id = 'BT25'
    name = 'RANGE_TO_TREND_TRANSITION'
    family = 'breakout'
    reversal = False
    supported_regimes = ('TREND_UP', 'TREND_DOWN', 'EXPANSION')
    defaults = {**BTStrategy.defaults, **{'range_observations': 2.0, 'transition_expansion': 1.1, 'transition_pressure': 50.0}}
    def trigger(self, bt, side):
        p=self.parameters
        range_history=sum(x.BT_REGIME=='RANGE' and x.features.get('range_valid',False) for x in bt.previous[-4:])
        ok=range_history>=p['range_observations'] and bt.features.get('breakout_side')==side and bt.features.get('atr_norm',0)>=p['transition_expansion'] and bt.BT_PRESSURE>=p['transition_pressure'] and not bt.features.get('failed_breakout_side')
        return ok,.95,'established range broke with expansion and directional pressure' if ok else 'range-to-trend transition not confirmed'

