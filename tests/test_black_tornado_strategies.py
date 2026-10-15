import pytest
from dataclasses import replace
from app.config import Settings
from app.strategies.registry import make_strategies
from tests.bt_fixtures import fixture

STRATEGIES=make_strategies(Settings())
CASES=[(s.strategy_id,side) for s in STRATEGIES for side in ((1,) if s.strategy_id=='BT16' else ((-1,) if s.strategy_id=='BT17' else (1,-1)))]

def module(sid): return next(s for s in STRATEGIES if s.strategy_id==sid)

def test_exactly_twenty_five():
    assert len(STRATEGIES)==25 and len({s.strategy_id for s in STRATEGIES})==25

@pytest.mark.parametrize('sid,side',CASES)
def test_independent_positive_trigger(sid,side):
    bt=fixture(sid,side)
    a=module(sid).assess(bt)
    assert a.candidate is not None,(sid,side,a.rejection)
    assert a.candidate.direction==('CALL' if side==1 else 'PUT')
    assert a.candidate.strategy==sid
    assert a.candidate.details['bt']['BT_DATA_OK']

@pytest.mark.parametrize('sid,side',CASES)
def test_trigger_rejection(sid,side):
    bt=fixture(sid,side)
    empty=replace(bt,features={},previous=())
    ok,quality,reason=module(sid).trigger(empty,side)
    assert not ok and reason

@pytest.mark.parametrize('sid',[s.strategy_id for s in STRATEGIES])
@pytest.mark.parametrize('gate',['data','turbulence','regime','confidence'])
def test_hard_rejections(sid,gate):
    side=-1 if sid=='BT17' else 1
    bt=fixture(sid,side)
    changes={'data':dict(BT_DATA_OK=False),'turbulence':dict(BT_TURBULENCE=99),
        'regime':dict(BT_REGIME='UNKNOWN'),'confidence':dict(BT_CONFIDENCE=0)}
    result=module(sid).assess(replace(bt,**changes[gate]))
    assert result.candidate is None and result.rejection

@pytest.mark.parametrize('sid',[s.strategy_id for s in STRATEGIES if s.strategy_id not in ('BT16','BT17')])
def test_opposite_direction_symmetry(sid):
    up=module(sid).assess(fixture(sid,1)).candidate
    down=module(sid).assess(fixture(sid,-1)).candidate
    assert up and down and abs(up.setup_score-down.setup_score)<1e-10

def test_floor_ceiling_mirror():
    assert module('BT16').assess(fixture('BT16',1)).candidate.direction=='CALL'
    assert module('BT17').assess(fixture('BT17',-1)).candidate.direction=='PUT'
