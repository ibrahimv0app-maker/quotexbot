"""BT23 — CANDLE_PRESSURE_SEQUENCE. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT23Strategy(BTStrategy):
    strategy_id = 'BT23'
    name = 'CANDLE_PRESSURE_SEQUENCE'
    family = 'continuation'
    reversal = False
    supported_regimes = ('TREND_UP', 'TREND_DOWN', 'EXPANSION')
    defaults = {**BTStrategy.defaults, **{'sequence_pressure': 60.0}}
    def trigger(self, bt, side):
        p=self.parameters
        prev=self.previous(bt)
        no_conflict=bt.features.get('failed_breakout_side',0)!=-side and bt.features.get('rejection_side',0)!=-side
        ok=prev is not None and bt.features.get('body_sequence_side')==side and self.pressure(bt,side)>=p['sequence_pressure'] and self.pressure(bt,side)>self.pressure(prev,side) and no_conflict
        return ok,.95,'three strong directional bodies and close positions; pressure growing' if ok else 'directional pressure sequence incomplete'

