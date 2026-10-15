import time
from app.feed.candle_store import CandleStore
from app.feed.client import Candle
from app.services.market_service import aggregate_m5,MarketService
from app.config import Settings

def test_live_close_and_late_tick():
    s=CandleStore(None,None)
    t=int(time.time())//60*60-120
    s.apply_tick('S',1,t);s.apply_tick('S',2,t+10);s.apply_tick('S',.5,t+20)
    
    for i in (30,40,50,59): s.apply_tick('S',.5,t+i)
    s.apply_tick('S',3,t+60)
    c=s.last_closed('S')
    assert (c.open,c.high,c.low,c.close)==(1,2,.5,.5)
    s.apply_tick('S',99,t+30)
    assert s.last_closed('S')==c

def test_rest_reconcile_updates_without_duplicates():
    s=CandleStore(None,None);t=int(time.time())//60*60-120
    a=Candle(t,1,2,.5,1,0);b=Candle(t,1,3,.5,2,0)
    s.merge_candles('S',[a]);s.merge_candles('S',[b])
    assert s.series('S')==[b]
def test_forming_not_closed():
    s=CandleStore(None,None);t=int(time.time())//60*60
    s.merge_candles('S',[Candle(t,1,2,.5,1,0)])
    assert s.closed_count('S')==0
def test_m5_requires_exact_five():
    t=300000
    bars=[Candle(t+i*60,1,2,.5,1,0) for i in range(5)]
    assert len(aggregate_m5(bars,t+300))==1
    assert aggregate_m5(bars[:-1],t+300)==[]
    assert aggregate_m5(bars,t+299)==[]
def test_future_stale_and_out_of_order_rejected():
    m=MarketService(Settings(SYMBOLS=['EURUSD-OTC']),None);t=int(time.time())
    m._on_tick('EURUSD-OTC',1,t+100,0)
    m._on_tick('EURUSD-OTC',1,t-100,0)
    m._on_tick('EURUSD-OTC',float('nan'),t,0)
    assert m.tick_count==0
    m._on_tick('EURUSD-OTC',1,t,0);m._on_tick('EURUSD-OTC',2,t-1,0)
    assert m.tick_count==1

def test_midminute_partial_not_closed():
    s=CandleStore(None,None);t=int(time.time())//60*60-120
    s.apply_tick('S',1,t+40)
    for sec in range(41,61): s.apply_tick('S',1,t+sec)
    assert s.last_closed('S') is None

def test_gap_does_not_fabricate_candles():
    s=CandleStore(None,None);t=int(time.time())//60*60-300
    s.apply_tick('S',1,t);s.apply_tick('S',1,t+180)
    assert s.closed_count('S')==0
