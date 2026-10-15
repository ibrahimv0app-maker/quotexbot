"""BT02 — MAIN_TORNADO_TREND. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT02Strategy(BTStrategy):
    strategy_id = 'BT02'
    name = 'MAIN_TORNADO_TREND'
    family = 'continuation'
    reversal = False
    supported_regimes = ('TREND_UP', 'TREND_DOWN')
    defaults = {**BTStrategy.defaults, **{'sustained_direction': 40.0, 'trend_pressure': 45.0}}
    def trigger(self, bt, side):
        p=self.parameters
        persistence=len(bt.previous)>=2 and all(self.trend(x,side) and side*x.BT_DIRECTION>=p['sustained_direction'] for x in bt.previous[-2:])
        ok=self.trend(bt,side) and persistence and side*bt.BT_DIRECTION>=p['sustained_direction'] and bt.BT_PRESSURE>=p['trend_pressure'] and bt.features.get('structure_held_side')==side and not bt.features.get('failed_breakout_side')
        return ok,.9,'persistent trend with intact structure' if ok else 'trend persistence/structure absent'

