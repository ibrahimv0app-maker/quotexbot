"""BT21 — SPIKE_COOLDOWN_CONTINUATION. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT21Strategy(BTStrategy):
    strategy_id = 'BT21'
    name = 'SPIKE_COOLDOWN_CONTINUATION'
    family = 'cooldown'
    reversal = False
    supported_regimes = ('TREND_UP', 'TREND_DOWN', 'EXPANSION')
    defaults = {**BTStrategy.defaults, **{'cooldown_age': 6.0, 'cooldown_drop': 15.0, 'cooldown_pressure': 45.0}}
    def trigger(self, bt, side):
        p=self.parameters
        age=bt.features.get('last_spike_age')
        peak=max((x.BT_TURBULENCE for x in bt.previous[-6:]),default=0)
        ok=age is not None and 2<=age<=p['cooldown_age'] and peak-bt.BT_TURBULENCE>=p['cooldown_drop'] and bt.features.get('structure_held_side')==side and bt.features.get('ema_trend_side')==side and bt.BT_PRESSURE>=p['cooldown_pressure']
        return ok,.9,'post-spike turbulence normalized; original structure and pressure hold' if ok else 'spike cooldown continuation not confirmed'

