import json,math,time,pytest
from dataclasses import replace
from app.black_tornado.core import BlackTornado,pivots,classify_regime
from app.black_tornado.config import BTConfig
from app.black_tornado.normalization import robust_z,signed,weighted_available
from app.config import Settings
from app.feed.client import Candle
from app.strategies.base import build_context

@pytest.fixture
def bars():
    t=(int(time.time())//60-280)*60
    return [Candle(t+i*60,10+.002*i+.02*math.sin(i/4),10+.002*i+.02*math.sin(i/4)+.012,
        10+.002*i+.02*math.sin(i/4)-.011,10+.002*i+.02*math.sin(i/4)+.008*math.sin(i),None) for i in range(260)]

def view(bars):
    ctx=build_context('S',bars[-1].close_time,bars,last_price=bars[-1].close,data_age=0)
    ctx.last_received_ts=ctx.now
    return ctx

def test_outputs_ranges_and_weights(bars):
    b=BlackTornado(Settings()).analyze(view(bars))
    assert b.BT_DATA_OK
    assert abs(b.BT_DIRECTION-.5*b.BT_TECHNICAL_DIRECTION-.5*b.BT_BEHAVIOR_DIRECTION)<1e-10
    for key in ['BT_DIRECTION','BT_TECHNICAL_DIRECTION','BT_BEHAVIOR_DIRECTION']: assert -100<=getattr(b,key)<=100
    for key in ['BT_CONFIDENCE','BT_PRESSURE','BT_TURBULENCE','BT_EXHAUSTION']: assert 0<=getattr(b,key)<=100
    snap=b.BT_FEATURE_SNAPSHOT
    json.dumps(snap,allow_nan=False)
    assert snap['confidence_is_probability'] is False and snap['sweep_is_price_proxy']

def test_deterministic_and_nonmutating_snapshot(bars):
    e=BlackTornado(Settings());a=e.analyze(view(bars));b=e.analyze(view(bars))
    assert a==b
    a.snapshot()['features']['atr']=999
    assert e.analyze(view(bars)).features['atr']!=999

def test_prefix_invariance_no_repaint(bars):
    e=BlackTornado(Settings())
    before=e.analyze(view(bars[:-1]));after=e.analyze(view(bars))
    historical=after.previous[-1]
    assert before.closed_through==historical.closed_through
    for name in ['BT_DIRECTION','BT_TECHNICAL_DIRECTION','BT_BEHAVIOR_DIRECTION','BT_PRESSURE','BT_REGIME']:
        assert getattr(before,name)==getattr(historical,name)

def test_future_and_partial_not_used(bars):
    e=BlackTornado(Settings());ctx=view(bars)
    a=e.analyze(ctx)
    garbage=replace(bars[-1],time=bars[-1].time+60,close=999,high=1000)
    assert e.analyze(replace(ctx,forming=garbage)).BT_DIRECTION==a.BT_DIRECTION
    assert not e.analyze(replace(ctx,candles=bars+[garbage])).BT_DATA_OK

def test_stale_and_gaps(bars):
    e=BlackTornado(Settings());ctx=view(bars)
    assert not e.analyze(replace(ctx,data_age=99)).BT_DATA_OK
    assert not e.analyze(replace(ctx,data_age=-1)).BT_DATA_OK
    assert not e.analyze(replace(ctx,candles=bars[:-3]+bars[-2:])).BT_DATA_OK

def test_flat_unknown_not_faked(bars):
    flat=[replace(c,open=1,high=1,low=1,close=1) for c in bars]
    bt=BlackTornado(Settings()).analyze(view(flat))
    assert not bt.BT_DATA_OK and bt.BT_REGIME=='UNKNOWN'

def test_price_scale_invariance(bars):
    e=BlackTornado(Settings());a=e.analyze(view(bars))
    scaled=[replace(c,open=c.open*100,high=c.high*100,low=c.low*100,close=c.close*100) for c in bars]
    b=e.analyze(view(scaled))
    assert b.BT_DIRECTION==pytest.approx(a.BT_DIRECTION,abs=1e-7)

def test_direction_mirrors(bars):
    e=BlackTornado(Settings());a=e.analyze(view(bars))
    mirrored=[replace(c,open=22-c.open,high=22-c.low,low=22-c.high,close=22-c.close) for c in bars]
    b=e.analyze(view(mirrored))
    assert b.BT_DIRECTION==pytest.approx(-a.BT_DIRECTION,abs=1e-7)

def test_pivot_confirmation_not_backdated(bars):
    hs,ls=pivots(bars)
    for p in hs+ls: assert p['confirmed_ts']==bars[p['index']+2].close_time
    assert all(p['index']<len(bars)-2 for p in hs+ls)

def test_robust_normalization():
    assert signed(999)<=100 and signed(-999)>=-100
    assert robust_z(1,[1]*20)==0
    assert robust_z(100,[1]*20)==6
    assert weighted_available({'a':50,'b':None},{'a':.5,'b':.5})==(50.,('b',))

@pytest.mark.parametrize('updates,expected',[
    ({'turbulence':99},'CHAOS'),({'exhaustion':90,'reversal_evidence':True},'REVERSAL_RISK'),
    ({'compressed':True},'SQUEEZE'),({'atr_norm':1.6},'EXPANSION'),
    ({'trend_side':1,'structure':100,'adx_value':30},'TREND_UP'),
    ({'trend_side':-1,'structure':-100,'adx_value':30},'TREND_DOWN'),
    ({'range_valid':True,'crossings':4},'RANGE'),({},'UNKNOWN')])
def test_regime_priorities(updates,expected):
    args=dict(turbulence=10,range_atr=1,exhaustion=10,reversal_evidence=False,compressed=False,atr_norm=1,
        breakout_side=0,trend_side=0,adx_value=15,structure=0,pressure_signed=0,range_valid=False,crossings=0)
    assert classify_regime(BTConfig(),**(args|updates))==expected

def test_unchanged_closed_bar_does_not_invent_new_history(bars):
    e=BlackTornado(Settings());ctx=view(bars);a=e.analyze(ctx)
    b=e.analyze(replace(ctx,now=ctx.now+1,last_price=ctx.last_price+.001,data_age=0))
    assert a.BT_DIRECTION==b.BT_DIRECTION
    assert [p.closed_through for p in a.previous]==[p.closed_through for p in b.previous]

def test_custom_weights_respect_domain_split(bars):
    cfg=BTConfig(technical_weights=dict(trend=1.,momentum=0.,movement=0.,oscillator=0.))
    b=BlackTornado(Settings(),cfg).analyze(view(bars))
    assert b.BT_TECHNICAL_DIRECTION==b.components['technical']['trend']
    assert b.BT_DIRECTION==.5*b.BT_TECHNICAL_DIRECTION+.5*b.BT_BEHAVIOR_DIRECTION

def test_missing_htf_is_disclosed_not_invented(bars):
    b=BlackTornado(Settings(),BTConfig(lookback=120)).analyze(view(bars))
    if b.components['behavior']['htf'] is None:
        assert 'htf' in b.missing and b.BT_HTF_ALIGNMENT=='NEUTRAL'

def test_closed_research_never_claims_live_data_ok(bars):
    b=BlackTornado(Settings()).analyze(replace(view(bars),last_price=None,data_age=float('inf')),require_live=False)
    assert not b.BT_DATA_OK and b.features['research_closed_only']
    assert b.features['closed_data_valid']

def test_future_receipt_cannot_enter_snapshot(bars):
    ctx=view(bars);ctx.last_received_ts=ctx.now+.01
    assert not BlackTornado(Settings()).analyze(ctx).BT_DATA_OK
    ctx.last_received_ts=None
    assert not BlackTornado(Settings()).analyze(ctx).BT_DATA_OK

def test_frame_cannot_be_mutated_or_cache_corrupted(bars):
    import pytest
    e=BlackTornado(Settings());b=e.analyze(view(bars))
    with pytest.raises(TypeError): b.features['atr']=999
    with pytest.raises(TypeError): b.previous[-1].features['atr']=999
    with pytest.raises(TypeError): e.config.technical_weights['trend']=999
    s=b.snapshot();s['features']['atr']=999
    assert e.analyze(view(bars)).features['atr']!=999
