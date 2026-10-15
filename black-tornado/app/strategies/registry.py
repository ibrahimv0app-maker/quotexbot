"""Exactly 25 independent BT modules; one shared intelligence engine."""
from importlib import import_module
from pathlib import Path
import json
from app.black_tornado.core import BlackTornado

MODULES = [('01', 'tornado_ignition'), ('02', 'main_tornado_trend'), ('03', 'adaptive_pullback'), ('04', 'shallow_retracement'), ('05', 'storm_acceleration'), ('06', 'fresh_structure_breakout'), ('07', 'breakout_retest'), ('08', 'squeeze_release'), ('09', 'first_impulse_after_compression'), ('10', 'm5_m1_alignment'), ('11', 'sweep_and_reclaim'), ('12', 'failed_breakout_trap'), ('13', 'structural_wick_rejection'), ('14', 'exhaustion_divergence'), ('15', 'overextension_snapback'), ('16', 'range_floor_bounce'), ('17', 'range_ceiling_fade'), ('18', 'mean_reversion_return'), ('19', 'double_sweep_trap'), ('20', 'failed_continuation_flip'), ('21', 'spike_cooldown_continuation'), ('22', 'spike_exhaustion_reversal'), ('23', 'candle_pressure_sequence'), ('24', 'trend_to_range_transition'), ('25', 'range_to_trend_transition')]

def make_strategies(settings, engine=None):
    engine = engine or BlackTornado(settings)
    path=Path(settings.STRATEGY_CONFIG_FILE)
    config=json.loads(path.read_text()) if path.is_file() else {}
    known={f'BT{n}' for n,_ in MODULES}
    if set(settings.BT_ENABLED_STRATEGIES)-known or set(config)-known:
        raise ValueError('Unknown BLACK TORNADO strategy ID')
    out=[]
    for n,name in MODULES:
        if f'BT{n}' in settings.BT_ENABLED_STRATEGIES:
            cls=getattr(import_module(f'app.strategies.bt{n}_{name}'),f'BT{n}Strategy')
            out.append(cls(engine,config.get(f'BT{n}',{})))
    return out
