from app.backtesting.reports import metrics
from app.backtesting.engine import ReplayQuotes,Backtester
from app.config import Settings

def test_denominator_draws_unverified():
    rows=[dict(outcome=x,entry_ts=i*60) for i,x in enumerate(['WIN','LOSS','DRAW','UNVERIFIED'])]
    m=metrics(rows)
    assert m['win_rate']==50 and m['sample_size']==4 and m['draws']==1 and m['unverified']==1

def test_replay_never_reads_future_or_unreceived():
    q=ReplayQuotes([dict(symbol='S',ts=99,price=1,received_ts=102),dict(symbol='S',ts=101,price=2,received_ts=101)])
    assert q.quote('S',100,2,available_by=100) is None
    assert q.quote('S',100,2,available_by=103)[1]==1

def test_candle_only_no_fake_outcome(candles):
    r=Backtester(Settings()).run({'S':candles})
    assert r['mode']=='candle_setups_only' and r['report']['overall']['sample_size']==0

def test_empty_enabled_registry_and_small_validation():
    from app.backtesting.validation import run_validation,walk_forward_windows
    from app.backtesting.engine import Backtester
    from app.config import Settings
    assert Backtester(Settings(BT_ENABLED_STRATEGIES=[])).run({})['records']==[]
    assert walk_forward_windows([])==[]
    r=run_validation(Settings(),{},[])
    assert r['walk_forward']==[] and len(r['sensitivity_validation_only'])==3
