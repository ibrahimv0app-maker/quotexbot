"""Causal fixed-window composite engine. Strategies never recalculate indicators.

Only closed M1 bars feed scores. A genuine, received-by-decision live observation
is a hard gate and a last-moment acceptance/rejection check, not a future candle.
Historical frames use exactly the same fixed lookback, so appending future bars
cannot revise a previously calculated frame. See docs/BLACK_TORNADO_MATH.md.
"""
from __future__ import annotations
import math,statistics,hashlib,json
from functools import lru_cache
from dataclasses import replace,asdict
from app.indicators.technical import ema,rsi,macd,atr,adx,bollinger
from app.services.market_service import aggregate_m5
from app.black_tornado.models import BTFrame
from app.black_tornado.config import BTConfig
from app.black_tornado.normalization import clip,signed,sign,robust_z,percentile,weighted_available


def pivots(bars,left=2,right=2):
    highs=[];lows=[]
    for i in range(left,len(bars)-right):
        wh=[c.high for c in bars[i-left:i+right+1]]
        wl=[c.low for c in bars[i-left:i+right+1]]
        if bars[i].high==max(wh) and wh.count(bars[i].high)==1:
            highs.append(dict(index=i,value=bars[i].high,confirmed_ts=bars[i+right].close_time))
        if bars[i].low==min(wl) and wl.count(bars[i].low)==1:
            lows.append(dict(index=i,value=bars[i].low,confirmed_ts=bars[i+right].close_time))
    return highs,lows

def anatomy(c):
    span=c.high-c.low
    if span<=0: return dict(body=0,upper=0,lower=0,close_position=0,pressure=0,side=0)
    body=(c.close-c.open)/span
    pos=(2*c.close-c.high-c.low)/span
    return dict(body=body,upper=(c.high-max(c.open,c.close))/span,
        lower=(min(c.open,c.close)-c.low)/span,close_position=pos,
        pressure=100*(.6*body+.4*pos),side=sign(c.close-c.open))

def classify_regime(cfg,turbulence,range_atr,exhaustion,reversal_evidence,compressed,atr_norm,breakout_side,trend_side,adx_value,structure,pressure_signed,range_valid,crossings):
    if turbulence>=cfg.chaos_turbulence or range_atr>cfg.chaos_range_atr: return 'CHAOS'
    if exhaustion>=cfg.reversal_exhaustion and reversal_evidence: return 'REVERSAL_RISK'
    if compressed: return 'SQUEEZE'
    if atr_norm>=cfg.expansion_atr_ratio or (breakout_side and range_atr>=1.4): return 'EXPANSION'
    if trend_side and adx_value>=cfg.trend_adx and (structure==trend_side*100 or abs(pressure_signed)>=45): return 'TREND_UP' if trend_side==1 else 'TREND_DOWN'
    if range_valid and adx_value<=cfg.range_adx and crossings>=2: return 'RANGE'
    return 'UNKNOWN'

class BlackTornado:
    def __init__(self,settings,config=None):
        self.settings=settings
        self.config=config or BTConfig.load(settings.BT_CONFIG_FILE)
        self.config_hash=hashlib.sha256(json.dumps(asdict(self.config),sort_keys=True).encode()).hexdigest()
        self._cached=lru_cache(maxsize=1024)(self._closed_frame)

    def analyze(self,ctx,require_live=True):
        cfg=self.config
        # Reject, rather than silently incorporate, future or misordered bars.
        allbars=list(ctx.candles)
        bad=[]
        if len(allbars)<cfg.lookback: bad.append('insufficient closed history')
        if any(c.close_time>ctx.now or c.time%60 for c in allbars): bad.append('future/unfinished candle')
        if any(allbars[i].time-allbars[i-1].time!=60 for i in range(max(1,len(allbars)-cfg.lookback-cfg.observation_history),len(allbars))): bad.append('missing/duplicate/out-of-order bars')
        if any(not all(math.isfinite(v) and v>0 for v in [c.open,c.high,c.low,c.close]) or c.low>min(c.open,c.close) or c.high<max(c.open,c.close) for c in allbars[-cfg.lookback:]): bad.append('invalid OHLC')
        if not allbars or bad:
            return BTFrame(ctx.symbol,ctx.now,allbars[-1].close_time if allbars else 0,missing=tuple(bad))
        base=self._cached(tuple(allbars[-cfg.lookback:]))
        if not base.BT_DATA_OK:
            return replace(base,symbol=ctx.symbol,decision_ts=ctx.now)
        previous=[]
        for n in range(min(cfg.observation_history,len(allbars)-cfg.lookback),0,-1):
            previous.append(self._cached(tuple(allbars[-cfg.lookback-n:-n])))
        if ctx.now-allbars[-1].close_time>65: bad.append('closed history stale')
        live=ctx.last_price
        if require_live and (live is None or not math.isfinite(live) or live<=0 or not 0<=ctx.data_age<=self.settings.DATA_STALE_SECONDS):
            bad.append('live data missing/stale/invalid')
        if require_live and (ctx.last_received_ts is None or ctx.last_received_ts>ctx.now): bad.append('receipt timestamp missing/after decision')
        features=dict(base.features)
        features['live_price']=live if require_live else None
        features['live_source_ts']=ctx.now-ctx.data_age if require_live and math.isfinite(ctx.data_age) else None
        features['live_received_ts']=ctx.last_received_ts if require_live else None
        features['data_age']=ctx.data_age if require_live and math.isfinite(ctx.data_age) else None
        features['research_closed_only']=not require_live
        features['closed_data_valid']=not bad
        features['live_move_atr']=(live-allbars[-1].close)/features['atr'] if live is not None and math.isfinite(live) else None
        features['live_beyond_level']=None
        if live is not None and features.get('event_level') is not None:
            features['live_beyond_level']=(live-features['event_level'])/features['atr']
        # Historical output sequences are closed-bar observations, not repeated
        # evaluations of the same unchanged candle counted as new confirmations.
        return replace(base,symbol=ctx.symbol,decision_ts=ctx.now,BT_DATA_OK=not bad and require_live,
            features=features,previous=tuple(previous),missing=tuple(bad)+base.missing+(() if require_live else ('no live observations; closed-only research',)))

    def _closed_frame(self,bars):
        cfg=self.config
        o=[c.open for c in bars];h=[c.high for c in bars];l=[c.low for c in bars];c=[x.close for x in bars]
        av=atr(h,l,c,cfg.atr_period);a=av[-1]
        if a is None or a<=0:
            return BTFrame('',bars[-1].close_time,bars[-1].close_time,missing=('ATR unavailable/inactive',))
        e9=ema(c,cfg.ema_fast);e21=ema(c,cfg.ema_mid);e50=ema(c,cfg.ema_slow)
        rs7=rsi(c,cfg.rsi_fast);rs14=rsi(c,cfg.rsi_slow)
        ml,ms,mh=macd(c,cfg.macd_fast,cfg.macd_slow,cfg.macd_signal);ad,pdi,mdi=adx(h,l,c,cfg.atr_period)
        mid,upper,lower,bw=bollinger(c,cfg.bb_period,cfg.bb_deviation)
        q=[anatomy(b) for b in bars]
        pp=[statistics.fmean(x['pressure'] for x in q[max(0,i-cfg.pressure_period+1):i+1]) for i in range(len(q))]
        tr=[max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])) if i else h[i]-l[i] for i in range(len(c))]
        reference=cfg.robust_period
        separations=dict(fast_mid=(e9[-1]-e21[-1])/a,mid_slow=(e21[-1]-e50[-1])/a)
        sep=.6*separations['fast_mid']+.4*separations['mid_slow']
        slopes={name:(series[-1]-series[-1-cfg.ema_slope_period])/(cfg.ema_slope_period*a) for name,series in [('fast',e9),('mid',e21),('slow',e50)]}
        slope=.5*slopes['fast']+.3*slopes['mid']+.2*slopes['slow']
        trend=signed(.7*sep+.9*slope)
        hist_values=[v/av[i] for i,v in enumerate(mh[:-1]) if v is not None and av[i]]
        zh=robust_z(mh[-1]/a,hist_values[-reference:])
        roc=(c[-1]-c[-1-cfg.roc_period])/a
        momentum=.4*signed((zh or 0)/2)+.35*signed(roc/2)+.25*clip((rs14[-1]-50)*2)
        denom=pdi[-1]+mdi[-1]
        movement=100*(pdi[-1]-mdi[-1])/denom if denom else 0
        movement*=.5+.5*min(ad[-1]/50,1)
        dev=(c[-1]-e21[-1])/a
        stochastic=100*(c[-1]-min(l[-cfg.stochastic_period:]))/(max(h[-cfg.stochastic_period:])-min(l[-cfg.stochastic_period:])) if max(h[-cfg.stochastic_period:])>min(l[-cfg.stochastic_period:]) else 50
        oscillator=.5*signed((rs7[-1]-rs7[-3])/10)+.25*clip((stochastic-50)*2)+.25*signed(dev/2)
        tech=dict(trend=trend,momentum=momentum,movement=movement,oscillator=oscillator)
        technical,_=weighted_available(tech,cfg.technical_weights)
        # Levels usable for the latest bar were confirmed BEFORE it opened.
        highs,lows=pivots(bars[:-1],cfg.pivot_left,cfg.pivot_right)
        highs=[p for p in highs if p['index']>=len(bars)-cfg.swing_lookback]
        lows=[p for p in lows if p['index']>=len(bars)-cfg.swing_lookback]
        upper_level=highs[-1]['value'] if highs else None
        lower_level=lows[-1]['value'] if lows else None
        hhhl=len(highs)>=2 and len(lows)>=2 and highs[-1]['value']>highs[-2]['value'] and lows[-1]['value']>lows[-2]['value']
        lhll=len(highs)>=2 and len(lows)>=2 and highs[-1]['value']<highs[-2]['value'] and lows[-1]['value']<lows[-2]['value']
        structure=100 if hhhl else (-100 if lhll else 0)
        structure_state='HH/HL' if hhhl else ('LH/LL' if lhll else ('MIXED' if len(highs)>=2 and len(lows)>=2 else 'UNCONFIRMED'))
        rb_high=statistics.median(p['value'] for p in highs[-3:]) if len(highs)>=2 else None
        rb_low=statistics.median(p['value'] for p in lows[-3:]) if len(lows)>=2 else None
        range_valid=bool(rb_high is not None and rb_low is not None and rb_high-rb_low>=2*a and max(p['value'] for p in highs[-3:])-min(p['value'] for p in highs[-3:])<=cfg.range_boundary_atr_tolerance*a and max(p['value'] for p in lows[-3:])-min(p['value'] for p in lows[-3:])<=cfg.range_boundary_atr_tolerance*a)
        events=[]
        for k in range(len(bars)-7,len(bars)):
            hs,ls=pivots(bars[:k],cfg.pivot_left,cfg.pivot_right)
            hi=hs[-1]['value'] if hs else None;lo=ls[-1]['value'] if ls else None
            b=bars[k];prev=bars[k-1];ak=av[k]
            direction=1 if hi is not None and b.close>hi+cfg.breakout_atr_buffer*ak and prev.close<=hi else (-1 if lo is not None and b.close<lo-cfg.breakout_atr_buffer*ak and prev.close>=lo else 0)
            sweep=1 if lo is not None and b.low<lo-cfg.breakout_atr_buffer*ak and b.close>lo and q[k]['lower']>=cfg.rejection_wick else (-1 if hi is not None and b.high>hi+cfg.breakout_atr_buffer*ak and b.close<hi and q[k]['upper']>=cfg.rejection_wick else 0)
            events.append(dict(age=len(bars)-1-k,breakout=direction,sweep=sweep,level=hi if direction==1 or sweep==-1 else (lo if direction==-1 or sweep==1 else None)))
        current=events[-1];prior_break=next((e for e in reversed(events[:-1]) if e['breakout']),None)
        breakout_side=current['breakout'];sweep_side=current['sweep']
        failed_side=0;retest_side=0;event_level=current['level']
        if prior_break:
            bs,bl=prior_break['breakout'],prior_break['level']
            if bs*(c[-1]-bl)<0 and sign(pp[-1])==-bs:
                failed_side=-bs;event_level=bl
            elif abs((l[-1] if bs==1 else h[-1])-bl)<=cfg.retest_atr_tolerance*a and bs*(c[-1]-bl)>0 and sign(pp[-1])==bs:
                retest_side=bs;event_level=bl
        rejection_side=1 if lower_level is not None and abs(l[-1]-lower_level)<=cfg.level_atr_tolerance*a and q[-1]['lower']>=cfg.rejection_wick and q[-1]['side']>=0 else (-1 if upper_level is not None and abs(h[-1]-upper_level)<=cfg.level_atr_tolerance*a and q[-1]['upper']>=cfg.rejection_wick and q[-1]['side']<=0 else 0)
        divergence_side=0;divergence_pivots=[]
        for ps,side in [(highs,-1),(lows,1)]:
            if len(ps)>=2:
                first,last=ps[-2:];p1,p2=pp[first['index']],pp[last['index']]
                new_extreme=last['value']>first['value'] if side==-1 else last['value']<first['value']
                weak=p2<p1-10 if side==-1 else p2>p1+10
                if new_extreme and weak:
                    divergence_side=side
                    divergence_pivots=[dict(**p,bt_pressure_signed=pp[p['index']]) for p in (first,last)]
        previous_pressure=statistics.fmean(pp[-6:-3])
        decline=max(0,abs(previous_pressure)-abs(pp[-1]))/100
        directional_wick=q[-1]['upper'] if sign(dev)>=0 else q[-1]['lower']
        exhaustion=clip(40*min(abs(dev)/3,1)+25*directional_wick+20*decline+15*bool(divergence_side),0,100)
        exhaustion_signed=(divergence_side or rejection_side)*exhaustion if divergence_side or rejection_side else 0
        m5=aggregate_m5(bars,bars[-1].close_time)
        ht=None;htf='NEUTRAL'
        if len(m5)>=24:
            mc=[b.close for b in m5];me=ema(mc,21);ma=atr([b.high for b in m5],[b.low for b in m5],mc)[-1]
            ht=signed(((mc[-1]-me[-1])+(me[-1]-me[-3]))/ma) if ma and ma>0 else 0
            htf='BULLISH' if ht>15 else ('BEARISH' if ht< -15 else 'NEUTRAL')
        behavior=dict(structure=structure if len(highs)>=2 and len(lows)>=2 else None,pressure=pp[-1],breakout=100*(failed_side or sweep_side or breakout_side or retest_side) if highs and lows else None,rejection=100*rejection_side if highs and lows else None,exhaustion=exhaustion_signed,htf=ht)
        behavior_direction,missing=weighted_available(behavior,cfg.behavior_weights)
        direction=.5*technical+.5*behavior_direction
        atr_pct=[v/c[i]*100 for i,v in enumerate(av) if v is not None]
        atr_norm=atr_pct[-1]/statistics.median(atr_pct[-reference:]) if statistics.median(atr_pct[-reference:])>0 else 0
        atr_percentile=percentile(atr_pct[-1],atr_pct[-reference-1:-1])
        widths=[w for w in bw if w is not None]
        width_pct=percentile(widths[-1],widths[-reference-1:-1])
        prior_width_pct=percentile(widths[-2],widths[-reference-2:-2])
        tr_z=robust_z(tr[-1],tr[-reference-1:-1])
        range_atr=tr[-1]/a
        wick_noise=statistics.fmean(1-abs(x['body']) for x in q[-5:])
        flips=sum(q[i]['side']!=q[i-1]['side'] for i in range(len(q)-5,len(q)))/5
        turbulence=clip(35*min(max(range_atr-1,0)/3,1)+25*min(max(tr_z or 0,0)/6,1)+20*wick_noise+20*flips,0,100)
        pressure=abs(pp[-1])
        crossings=sum((c[i]-e21[i])*(c[i-1]-e21[i-1])<0 for i in range(len(c)-20,len(c)))
        compressed=width_pct<=cfg.squeeze_percentile and atr_percentile<=cfg.squeeze_percentile
        trend_side=1 if direction>=cfg.min_trend_direction and e9[-1]>e21[-1]>e50[-1] else (-1 if direction<=-cfg.min_trend_direction and e9[-1]<e21[-1]<e50[-1] else 0)
        regime=classify_regime(cfg,turbulence,range_atr,exhaustion,bool(rejection_side or divergence_side or failed_side),compressed,atr_norm,breakout_side,trend_side,ad[-1],structure,pp[-1],range_valid,crossings)
        signs=[sign(x) for x in list(tech.values())+list(v for v in behavior.values() if v is not None) if abs(x)>5]
        agreement=sum(x==sign(direction) for x in signs)/len(signs) if signs else 0
        domains=1-abs(technical-behavior_direction)/200
        persistence=1-sum(q[i]['side']!=q[i-1]['side'] for i in range(len(q)-4,len(q)))/4
        confidence=clip(100*(.3*agreement+.3*domains+.2*persistence+.2*(regime not in ('CHAOS','UNKNOWN'))),0,100)
        last_spike=next((len(bars)-1-i for i in range(len(bars)-1,len(bars)-cfg.max_spike_age-2,-1) if tr[i]/(av[i-1] or a)>=2.5),None)
        matching_sweeps=[e for e in events if e['sweep']==sweep_side and e['level'] is not None and current['level'] is not None and abs(e['level']-current['level'])<=.5*a]
        double_sweep=sweep_side if sweep_side and len(matching_sweeps)>=2 else 0
        range_location=(c[-1]-rb_low)/(rb_high-rb_low) if range_valid else None
        structure_held=1 if lower_level is not None and c[-1]>=lower_level and trend_side==1 else (-1 if upper_level is not None and c[-1]<=upper_level and trend_side==-1 else 0)
        # Distinct mean/retracement observations are computed centrally.
        mean_rejection=1 if abs(l[-1]-e21[-1])<=.6*a and c[-1]>e21[-1] and q[-1]['lower']>=.3 else (-1 if abs(h[-1]-e21[-1])<=.6*a and c[-1]<e21[-1] and q[-1]['upper']>=.3 else 0)
        shallow=trend_side if trend_side and q[-2]['side']==-trend_side and q[-1]['side']==trend_side and tr[-2]<=1.2*a else 0
        features=dict(ema_values=dict(fast=e9[-1],mid=e21[-1],slow=e50[-1]),ema_slopes_atr=slopes,ema_separations_atr=separations,mean_rejection_side=mean_rejection,shallow_retracement_side=shallow,resume_side=sign(c[-1]-c[-2]),breakout_distance_atr=abs(c[-1]-event_level)/a if event_level is not None else 0,atr=a,atr_pct=atr_pct[-1],atr_norm=atr_norm,atr_percentile=atr_percentile,bb_width_percentile=width_pct,prior_width_percentile=prior_width_pct,
            tr_z=tr_z,range_atr=range_atr,adaptive_mean=e21[-1],deviation_atr=dev,mean_distance_atr=abs(dev),ema_trend_side=trend_side,
            pressure_signed=pp[-1],previous_pressure_signed=previous_pressure,body_signed=q[-1]['body'],body_ratio=abs(q[-1]['body']),upper_wick=q[-1]['upper'],lower_wick=q[-1]['lower'],close_position=q[-1]['close_position'],
            body_sequence_side=1 if all(x['body']>=.5 and x['close_position']>=.5 for x in q[-3:]) else (-1 if all(x['body']<=-.5 and x['close_position']<=-.5 for x in q[-3:]) else 0),
            breakout_side=breakout_side,failed_breakout_side=failed_side,retest_side=retest_side,sweep_side=sweep_side,rejection_side=rejection_side,divergence_side=divergence_side,double_sweep_side=double_sweep,
            event_level=event_level,prior_breakout=prior_break,support=lower_level,resistance=upper_level,range_valid=range_valid,range_low=rb_low,range_high=rb_high,range_location=range_location,
            structure_held_side=structure_held,hhhl=hhhl,lhll=lhll,last_spike_age=last_spike,compression=compressed,adx=ad[-1],rsi7=rs7[-1],rsi14=rs14[-1],stochastic=stochastic,
            confirmed_highs=highs[-3:],confirmed_lows=lows[-3:],divergence_pivots=divergence_pivots,wick_noise=wick_noise,mean_crossings=crossings,
            source_bars_hash=hashlib.sha256(json.dumps([b.as_dict() for b in bars],sort_keys=True).encode()).hexdigest())
        return BTFrame('',bars[-1].close_time,bars[-1].close_time,clip(direction),clip(technical),clip(behavior_direction),confidence,pressure,turbulence,exhaustion,regime,structure_state,
            'BULLISH_RECLAIM' if sweep_side==1 else ('BEARISH_RECLAIM' if sweep_side==-1 else 'NONE'),
            'FAILED_BREAKOUT' if failed_side else ('UPSIDE_BREAKOUT' if breakout_side==1 else ('DOWNSIDE_BREAKOUT' if breakout_side==-1 else 'NONE')),
            htf,True,features,dict(config_hash=self.config_hash,technical=tech,behavior=behavior,technical_weights=cfg.technical_weights,behavior_weights=cfg.behavior_weights,domain_weights=dict(technical=.5,behavior=.5)),missing)
