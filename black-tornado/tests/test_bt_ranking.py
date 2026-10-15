from dataclasses import replace
import pytest
from app.config import Settings
from app.strategies.registry import make_strategies
from app.engine.candidate_scorer import CandidateScorer
from app.services.scanner import resolve_conflicts
from tests.bt_fixtures import fixture

def candidate(sid='BT02',side=1):
    st=next(s for s in make_strategies(Settings()) if s.strategy_id==sid)
    return st.assess(fixture(sid,side)).candidate

def test_interpretable_rank_formula():
    c=candidate();r=CandidateScorer(Settings()).score(None,c)
    assert r.available_weight==90
    assert r.score==pytest.approx(100*sum(r.components.values())/90)
    assert 'performance' not in r.components and 'dropped' in r.performance_note

def test_no_vote_inflation_and_same_setup_dedup():
    scorer=CandidateScorer(Settings())
    a=scorer.score(None,candidate());b=scorer.score(None,candidate('BT05'))
    chosen=resolve_conflicts([a,b]*10)
    assert len(chosen)==1 and chosen[0].score==max(a.score,b.score)

def test_opposed_qualified_strategies_discard_pair():
    scorer=CandidateScorer(Settings())
    assert resolve_conflicts([scorer.score(None,candidate()),scorer.score(None,candidate(side=-1))])==[]

def test_small_or_wrong_version_performance_dropped():
    c=candidate();sc=CandidateScorer(Settings())
    p=dict(strategy=c.strategy,symbol=c.symbol,test_end_ts=c.details['bt']['decision_ts']-1,split='test',source='tick_replay',wins=2,losses=0,engine_version='BLACK_TORNADO_1.0',config_hash=c.details['config_hash'])
    assert sc.score(None,c,p).performance_sample is None
    p.update(wins=60,losses=40,engine_version='OLD')
    assert sc.score(None,c,p).performance_sample is None
    p['engine_version']='BLACK_TORNADO_1.0'
    assert sc.score(None,c,p).performance_sample==100
    p['test_end_ts']=c.details['bt']['decision_ts']+1
    assert sc.score(None,c,p).performance_sample is None

def test_invalid_data_cannot_rank():
    c=candidate();c.details['bt']['BT_DATA_OK']=False
    assert CandidateScorer(Settings()).score(None,c).score==0
