"""SYNTHETIC contract fixtures only. Never used as market or performance data."""
from dataclasses import replace
from app.black_tornado.models import BTFrame

def fixture(sid,side=1):
    regime='TREND_UP' if side==1 else 'TREND_DOWN'
    f=dict(atr=1.,atr_pct=.1,atr_norm=1.2,mean_distance_atr=1.,deviation_atr=side,
        pressure_signed=75*side,body_signed=.7*side,body_ratio=.7,lower_wick=.5 if side==1 else .1,upper_wick=.5 if side==-1 else .1,
        breakout_side=side,failed_breakout_side=0,sweep_side=side,rejection_side=side,retest_side=side,
        divergence_side=side,double_sweep_side=side,body_sequence_side=side,structure_held_side=side,
        ema_trend_side=side,resume_side=side,shallow_retracement_side=side,mean_rejection_side=side,
        range_valid=True,range_location=.1 if side==1 else .9,event_level=None,live_beyond_level=None,
        range_atr=1.5,compression=False,breakout_distance_atr=.3,prior_breakout={'age':2,'breakout':side},
        divergence_pivots=[{'confirmed_ts':800},{'confirmed_ts':900}],last_spike_age=3)
    base=BTFrame('S',1000,960,side*60,side*60,side*60,85,75,20,80,regime,
        'HH/HL' if side==1 else 'LH/LL','BULLISH_RECLAIM' if side==1 else 'BEARISH_RECLAIM',
        'UPSIDE_BREAKOUT' if side==1 else 'DOWNSIDE_BREAKOUT','BULLISH' if side==1 else 'BEARISH',True,f,
        {'config_hash':'synthetic-test-only'})
    previous=tuple(replace(base,closed_through=780+i*60,decision_ts=780+i*60,BT_DIRECTION=side*(30+i*10),
        BT_PRESSURE=40+i*10,features={**f,'pressure_signed':side*(40+i*10),'mean_distance_atr':.7,'range_atr':.8}) for i in range(3))
    if sid in ('BT01','BT08','BT09','BT25'): base=replace(base,BT_REGIME='EXPANSION')
    if sid=='BT01': previous=tuple(replace(x,BT_REGIME='RANGE') for x in previous)
    if sid in ('BT08','BT09'): previous=tuple(replace(x,BT_REGIME='SQUEEZE',features={**x.features,'compression':True}) for x in previous)
    if sid in ('BT11','BT13','BT16','BT17','BT18','BT19','BT24'): base=replace(base,BT_REGIME='RANGE')
    if sid in ('BT12','BT14','BT15','BT20','BT22'): base=replace(base,BT_REGIME='REVERSAL_RISK')
    if sid=='BT12':
        f={**f,'failed_breakout_side':side,'prior_breakout':{'age':2,'breakout':-side}}
        previous=previous[:-1]+(replace(previous[-1],BT_DIRECTION=30*side),)
    if sid=='BT15': f={**f,'deviation_atr':-2.5*side,'mean_distance_atr':2.5}
    if sid=='BT18':
        f={**f,'deviation_atr':-side}
        previous=previous[:-1]+(replace(previous[-1],features={**previous[-1].features,'deviation_atr':-2*side}),)
    if sid=='BT20':
        f={**f,'failed_breakout_side':side}
        previous=(replace(previous[0],BT_DIRECTION=-40*side),previous[1],replace(previous[2],BT_DIRECTION=30*side))
    if sid=='BT21': previous=(replace(previous[0],BT_TURBULENCE=65),)+previous[1:]
    if sid=='BT24': previous=tuple(replace(x,BT_PRESSURE=95) for x in previous)
    if sid=='BT25': previous=tuple(replace(x,BT_REGIME='RANGE') for x in previous)
    return replace(base,features=f,previous=previous)
