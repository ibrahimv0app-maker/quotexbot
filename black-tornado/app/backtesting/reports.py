"""Honest counts, denominators and consecutive-loss statistics."""
from collections import Counter, defaultdict
from datetime import datetime,timezone

def metrics(records):
    counts = Counter(r.get('outcome','UNVERIFIED') for r in records)
    wins,losses = counts['WIN'],counts['LOSS']
    streak = longest = 0
    for r in sorted(records,key=lambda r:r['entry_ts']):
        if r['outcome']=='LOSS': streak += 1; longest = max(longest,streak)
        elif r['outcome'] in ('WIN','DRAW'): streak = 0
    decided = wins+losses
    start = min((r['entry_ts'] for r in records),default=0)
    end = max((r['entry_ts'] for r in records),default=0)
    n = len(records)
    return dict(sample_size=n,wins=wins,losses=losses,draws=counts['DRAW'],unverified=counts['UNVERIFIED'],
        win_rate=100*wins/decided if decided else None,loss_rate=100*losses/decided if decided else None,
        draw_rate=100*counts['DRAW']/n if n else None,unverified_rate=100*counts['UNVERIFIED']/n if n else None,
        max_consecutive_losses=longest,signals_per_hour=n*3600/(end-start) if end>start else None)

def report(records):
    groups = defaultdict(list)
    for r in records: groups[(r['symbol'],r['strategy'],r['split'])].append(r)
    regimes = defaultdict(list)
    periods = defaultdict(list)
    for row in records:
        regimes[row.get('volatility_regime','unknown')].append(row)
        periods[datetime.fromtimestamp(row['entry_ts'],timezone.utc).strftime('%Y-%m-%d')].append(row)
    return dict(by_regime={k:metrics(v) for k,v in regimes.items()},by_utc_date={k:metrics(v) for k,v in periods.items()},overall=metrics(records),by_pair_strategy_split=[dict(symbol=k[0],strategy=k[1],split=k[2],
        **metrics(rows)) for k,rows in sorted(groups.items())])
