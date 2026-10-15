"""Expanding chronological windows, frozen-parameter sensitivity and multiplicity
reporting. No optimizer is permitted to reuse the final held-out period."""
from dataclasses import replace
from app.black_tornado.config import BTConfig
from app.backtesting.engine import Backtester

def walk_forward_windows(entries,folds=3):
    """Initial half for training, then nonoverlapping validation/test blocks."""
    if len(entries)<8: return []
    n=len(entries);block=max(1,n//(2*(folds+1)))
    windows=[]
    for k in range(folds):
        train_end=n//2+k*block
        valid_end=min(train_end+block,n-1)
        test_end=min(valid_end+block,n)
        if valid_end>=test_end: break
        windows.append(dict(train_end=entries[train_end],validation_end=entries[valid_end],test_end=entries[test_end-1]))
    return windows

def run_validation(settings,candles,quotes,folds=3):
    bt=Backtester(settings)
    decisions=sorted({c.close_time-settings.SIGNAL_LEAD_SECONDS for cs in candles.values() for c in cs})
    if quotes:
        lo=min(q['received_ts'] for q in quotes);hi=max(q['received_ts'] for q in quotes)
        decisions=[t for t in decisions if lo<=t<=hi]
    windows=walk_forward_windows(decisions,folds)
    results=[]
    for w in windows:
        capped={s:[c for c in cs if c.close_time<=w['test_end']+settings.SIGNAL_LEAD_SECONDS] for s,cs in candles.items()}
        r=bt.run(capped,quotes,folds=w)
        # Only a window's own held-out suffix contributes to its test metrics.
        from app.backtesting.reports import metrics
        results.append(dict(boundaries=w,test=metrics([x for x in r['records'] if x['split']=='test']),per_strategy_test={sid:metrics([x for x in rows if x['split']=='test']) for sid,rows in r['independent_records'].items()}))
    # Predeclared sensitivity grid, validation-only. Final test must not guide choice.
    base_bounds=dict(train_end=decisions[int(len(decisions)*.6)],validation_end=decisions[int(len(decisions)*.8)],test_end=decisions[-1]) if decisions else {}
    sensitivity=[]
    for threshold in (30,35,40):
        config=replace(bt.engine.config,min_trend_direction=threshold)
        from app.black_tornado.core import BlackTornado
        bt.engine=BlackTornado(settings,config=config)
        capped={s:[c for c in cs if c.close_time<base_bounds['validation_end']+settings.SIGNAL_LEAD_SECONDS] for s,cs in candles.items()} if base_bounds else candles
        r=bt.run(capped,quotes,folds=base_bounds or None)
        from app.backtesting.reports import metrics
        sensitivity.append(dict(min_trend_direction=threshold,validation=metrics([x for x in r['records'] if x['split']=='validation']),setups=sum(r['setup_counts'].values())))
    return dict(walk_forward=results,sensitivity_validation_only=sensitivity,independent_hypotheses=25,
        multiplicity='No significance/profitability claim. For 25 hypotheses, a naive 0.05 discovery threshold would require at least Bonferroni 0.05/25 = 0.002; correlated search and repeated tuning require stronger study design.',
        deployment_gate='Paper only until adequate held-out samples AND forward review; no module is promoted by best historical win rate.')
