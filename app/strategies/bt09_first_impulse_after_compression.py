"""BT09 — FIRST_IMPULSE_AFTER_COMPRESSION. Research hypothesis; see strategy catalog."""
from app.strategies.bt_base import BTStrategy

class BT09Strategy(BTStrategy):
    strategy_id = 'BT09'
    name = 'FIRST_IMPULSE_AFTER_COMPRESSION'
    family = 'breakout'
    reversal = False
    supported_regimes = ('EXPANSION', 'TREND_UP', 'TREND_DOWN')
    defaults = {**BTStrategy.defaults, **{'quiet_range': 1.0, 'impulse_min': 1.2, 'impulse_max': 2.2, 'impulse_body': 0.65}}
    def trigger(self, bt, side):
        p=self.parameters
        prior=list(bt.previous[-3:])
        quiet=len(prior)==3 and all(x.features.get('range_atr',999)<=p['quiet_range'] for x in prior) and any(x.BT_REGIME in ('SQUEEZE','RANGE') for x in prior)
        ok=quiet and bt.features.get('breakout_side')==side and p['impulse_min']<=bt.features.get('range_atr',0)<=p['impulse_max'] and bt.features.get('body_ratio',0)>=p['impulse_body']
        return ok,.95,'first bounded impulse after confirmed compression' if ok else 'late/unconfirmed first impulse'

