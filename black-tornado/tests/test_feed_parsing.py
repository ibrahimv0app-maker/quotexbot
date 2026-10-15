import time,pytest,math
from app.feed.client import parse_candles,FeedError
from app.feed.symbol_registry import SymbolRegistry
from app.config import DOCUMENTED_SYMBOLS,Settings

def payload():
    t = int(time.time())//60*60-120
    return dict(symbol='EURUSD-OTC',candles=[dict(time=t,open=1,high=2,low=.5,close=1.5,volume=1)])
def test_real_shape():
    c = parse_candles(payload(),'EURUSD-OTC')[0]
    assert c.close_time==c.time+60 and c.is_closed
@pytest.mark.parametrize('change',[{'time':12},{'high':.1},{'low':3},{'open':0},{'close':float('nan')},{'close':float('inf')}])
def test_invalid_ohlc(change):
    d=payload();d['candles'][0].update(change)
    with pytest.raises(FeedError): parse_candles(d)
def test_duplicates():
    d=payload();d['candles']*=2
    with pytest.raises(FeedError): parse_candles(d)
def test_empty_history_is_not_500(): assert parse_candles(dict(symbol='BTC-OTC',candles=[]))==[]
def test_symbol_mismatch():
    with pytest.raises(FeedError): parse_candles(payload(),'BRLUSD-OTC')
def test_aliases():
    r=SymbolRegistry(DOCUMENTED_SYMBOLS)
    assert r.normalise('EURUSD-OTCq')=='EURUSD-OTC'
    assert r.normalise('USDBRL-OTC') is None
    assert r.normalise('USDBRL-OTCq') is None
    assert r.normalise('INTC-OTC') is None
    assert [len(c) for c in r.chunks(10)]==[10,10,10,10,8]
@pytest.mark.parametrize('kw',[dict(SIGNAL_LEAD_SECONDS=9),dict(MAX_ACTIVE_SIGNALS=2),dict(SCAN_INTERVAL_SECONDS=2),dict(EXPIRY_SECONDS=120),dict(MAX_SYMBOLS_PER_CONNECTION=11),dict(DRY_RUN=False)])
def test_config_rejects(kw):
    with pytest.raises(ValueError): Settings(**kw)
def test_postgres_url(): assert Settings(DATABASE_URL='postgresql://u:p@host/db').DATABASE_URL.startswith('postgresql+asyncpg:')
