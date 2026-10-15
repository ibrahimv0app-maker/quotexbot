import pytest
from app.indicators.technical import *
from app.strategies.base import build_context

def test_ema_seed(): assert ema([1,2,3,4],3)==[None,None,2,3]
def test_sma(): assert sma([1,2,3,4],2)==[None,1.5,2.5,3.5]
def test_rsi_flat(): assert rsi([1]*30)[-1]==50
def test_rsi_trend(): assert rsi(list(range(30)))[-1]==100
@pytest.mark.parametrize('function',[ema,rsi])
def test_prefix_invariance(function):
    xs=[1+(i%7)*.1+i*.001 for i in range(80)]
    assert function(xs,14)[:50]==function(xs[:50],14)
def test_bollinger_constant():
    m,u,l,w=bollinger([10]*30)
    assert (m[-1],u[-1],l[-1],w[-1])==(10,10,10,0)
def test_atr(): assert atr([2]*30,[1]*30,[1.5]*30)[-1]==1
def test_macd_lengths():
    a,b,c=macd(list(range(80)))
    assert len(a)==len(b)==len(c)==80 and c[-1] is not None
def test_adx_last_defined():
    a,p,m=adx([i+2 for i in range(80)],[i+1 for i in range(80)],[i+1.5 for i in range(80)])
    assert a[-1] is not None and 0<=a[-1]<=100
def test_context_atr_computed(candles):
    ctx=build_context('S',candles[-1].close_time,candles,last_price=1)
    assert ctx.atr14>0 and ctx.candle_quality.range_atr>0
