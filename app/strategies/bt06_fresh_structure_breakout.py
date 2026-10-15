"""BT06 — FRESH_STRUCTURE_BREAKOUT. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT06Strategy(BTStrategy):
    strategy_id = 'BT06'
    name = 'FRESH_STRUCTURE_BREAKOUT'
    family = 'breakout'
    reversal = False
    supported_regimes = ('TREND_UP', 'TREND_DOWN', 'EXPANSION')
    defaults = {**BTStrategy.defaults, **{'min_break_distance': 0.1, 'break_direction': 35.0, 'break_body': 0.5}}
    def trigger(self, bt, side):
        p=self.parameters
        distance=bt.features.get('breakout_distance_atr',0)
        ok=bt.features.get('breakout_side')==side and distance>=p['min_break_distance'] and side*bt.BT_DIRECTION>=p['break_direction'] and bt.features.get('body_ratio',0)>=p['break_body']
        return ok,.95,'fresh confirmed-level break with displacement' if ok else 'no fresh qualified structure break'

