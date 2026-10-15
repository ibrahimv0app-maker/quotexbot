"""Causal BLACK TORNADO replay. Shared feature evaluation, independent module
lifecycles plus one global selector, explicit held-out periods, no invented ticks.
"""
from __future__ import annotations
import bisect,json
from collections import defaultdict,Counter
from pathlib import Path
from app.strategies.base import build_context
from app.services.scanner import make_strategies,resolve_conflicts
from app.engine.regime_filter import RegimeFilter
from app.engine.candidate_scorer import CandidateScorer
from app.engine.outcome_tracker import evaluate_direction
from app.backtesting.reports import report

class ReplayQuotes:
    def __init__(self,rows):
        self.data=defaultdict(list)
        for r in rows:
            if 'received_ts' in r: self.data[r['symbol']].append((int(r['ts']),float(r['price']),float(r['received_ts'])))
        self.times={}
        for s,qs in self.data.items():
            qs.sort(key=lambda q:(q[0],q[2]));self.times[s]=[q[0] for q in qs]
    def quote(self,symbol,boundary,tolerance,available_by=None):
        rows=self.data.get(symbol,[]);ts=self.times.get(symbol,[])
        i=bisect.bisect_right(ts,boundary)
        j=bisect.bisect_left(ts,boundary-tolerance)
        return max((q for q in rows[j:i] if available_by is None or q[2]<=available_by),default=None,key=lambda q:(q[0],q[2]))

class Backtester:
    def __init__(self,settings):
        self.settings=settings
        self.strategies=make_strategies(settings)
        from app.black_tornado.core import BlackTornado
        self.engine=self.strategies[0].engine if self.strategies else BlackTornado(settings)
        self.filter=RegimeFilter(settings);self.scorer=CandidateScorer(settings)
    def run(self,candles,quotes=None,strategy=None,folds=None):
        cfg=self.settings;qs=ReplayQuotes(quotes or [])
        bars={s:sorted(cs,key=lambda c:c.time) for s,cs in candles.items()}
        closes={s:[c.close_time for c in cs] for s,cs in bars.items()}
        entries=sorted(set(c.close_time for cs in bars.values() for c in cs))
        if quotes:
            low=min(q['received_ts'] for q in quotes);high=max(q['received_ts'] for q in quotes)
            entries=[t for t in entries if low<=t-cfg.SIGNAL_LEAD_SECONDS<=high]
        strategies=[s for s in self.strategies if strategy is None or s.strategy_id==strategy]
        ids=[s.strategy_id for s in strategies]
        per={sid:[] for sid in ids};records=[];setups=Counter();rejects=Counter();active=defaultdict(int)
        if not entries: return self._result(records,per,setups,rejects,{},bool(quotes))
        decisions=[t-cfg.SIGNAL_LEAD_SECONDS for t in entries]
        bounds=folds or dict(train_end=decisions[int(len(decisions)*.6)],validation_end=decisions[int(len(decisions)*.8)],test_end=decisions[-1])
        for entry,decision in zip(entries,decisions):
            split='train' if decision<bounds['train_end'] else ('validation' if decision<bounds['validation_end'] else 'test')
            if decision+cfg.SIMULATED_NOTIFICATION_LATENCY_SECONDS>entry-10:
                rejects['missed_notification_window']+=1;continue
            next_cut=bounds['train_end'] if split=='train' else (bounds['validation_end'] if split=='validation' else None)
            if next_cut is not None and entry+60+cfg.RESULT_TIMEOUT_SECONDS>=next_cut:
                rejects['purged_overlapping_label_horizon']+=1;continue
            ranked=[]
            for sym,cs in bars.items():
                cut=bisect.bisect_right(closes[sym],decision)
                history=cs[max(0,cut-320):cut]
                if len(history)<self.engine.config.lookback: continue
                q=qs.quote(sym,decision,cfg.DATA_STALE_SECONDS,decision)
                ctx=build_context(sym,decision,history,last_price=q[1] if q else None,data_age=decision-q[0] if q else float('inf'))
                ctx.last_received_ts=q[2] if q else None
                bt=self.engine.analyze(ctx,require_live=bool(quotes))
                if not quotes:
                    for st in strategies:
                        if st.closed_setups(bt): setups[f'{st.strategy_id}|{sym}|{split}']+=1
                    continue
                for st in strategies:
                    assessment=st.assess(bt)
                    cand=assessment.candidate
                    if cand is None: rejects[st.strategy_id+': '+assessment.rejection]+=1;continue
                    setups[f'{st.strategy_id}|{sym}|{split}']+=1
                    if not quotes or not q:
                        rejects['no_recorded_decision_tick']+=1;continue
                    f=self.filter.apply(ctx,cand)
                    if not f.passed: rejects[f.rejection]+=1;continue
                    cand.filters_passed=f.filters_passed
                    scored=self.scorer.score(ctx,cand)
                    if scored.score>=cfg.MIN_SETUP_SCORE: ranked.append(scored)
                    else: rejects['below_ranking_threshold']+=1
            for sid in ['GLOBAL']+ids:
                candidates=ranked if sid=='GLOBAL' else [r for r in ranked if r.candidate.strategy==sid]
                eligible=resolve_conflicts(candidates)
                if not eligible: continue
                if decision<active[sid]: rejects[sid+': lifecycle_active']+=1;continue
                r=self._record(eligible[0],qs,entry,decision,split)
                active[sid]=entry+60+(cfg.RESULT_TIMEOUT_SECONDS if r['outcome']=='UNVERIFIED' else 0)
                (records if sid=='GLOBAL' else per[sid]).append(r)
        return self._result(records,per,setups,rejects,bounds,bool(quotes))
    def _record(self,best,qs,entry,decision,split):
        cfg=self.settings;c=best.candidate;sym=c.symbol;expiry=entry+60
        eq=qs.quote(sym,entry,cfg.ENTRY_QUOTE_TOLERANCE_SECONDS,entry)
        xq=qs.quote(sym,expiry,cfg.EXPIRY_QUOTE_TOLERANCE_SECONDS,expiry)
        outcome=evaluate_direction(c.direction,eq[1],xq[1]) if eq and xq else 'UNVERIFIED'
        return dict(symbol=sym,strategy=c.strategy,direction=c.direction,score=best.score,components=best.components,
            split=split,decision_ts=decision,entry_ts=entry,expiry_ts=expiry,
            decision_quote=qs.quote(sym,decision,cfg.DATA_STALE_SECONDS,decision),entry_quote=eq,expiry_quote=xq,
            outcome=outcome,source='tick_replay',outcome_source='feed_estimated',
            engine_version='BLACK_TORNADO_1.0',config_hash=c.details['config_hash'],
            volatility_regime=c.details['bt']['BT_REGIME'],bt_snapshot=c.details['bt'])
    def _result(self,records,per,setups,rejects,bounds,ticks):
        return dict(report=report(records),records=records,independent_records=per,setup_counts=dict(setups),skipped=dict(rejects),split_boundaries=bounds,
            mode='tick_replay' if ticks else 'candle_setups_only',engine_version='BLACK_TORNADO_1.0',
            selection_bias_note='25 correlated hypotheses; default modules are paper research, not enabled on proof of historical performance. No final-test tuning or probability calibration.',
            limitation='Candle-only counts are setups, not timestamp-accurate trades. Zero verified outcomes is not proof that a strategy wins or loses.')
    def save(self,result,directory,include_independent=True):
        out=Path(directory);out.mkdir(parents=True,exist_ok=True)
        (out/'report.json').write_text(json.dumps(result,indent=2))
        m=result['report']['overall']
        lines=['# BLACK TORNADO replay report','',f"Mode: {result['mode']}",'',result['limitation'],'',
            f"Eligible selected signals: {m['sample_size']} | Wins: {m['wins']} | Losses: {m['losses']} | Draws: {m['draws']} | Unverified: {m['unverified']} | Win rate: {m['win_rate']}",
            '', '| Strategy / pair / split | Closed-candle setups (NOT verified trades) |','|---|---:|']
        lines += [f'|{key}|{value}|' for key,value in sorted(result['setup_counts'].items())]
        lines += ['',result['selection_bias_note'],'','Split boundaries: '+str(result['split_boundaries'])]
        (out/'report.md').write_text('\n'.join(lines)+'\n')
        artifact=[]
        for row in result['report']['by_pair_strategy_split']:
            n=row['wins']+row['losses']
            if result['mode']=='tick_replay' and row['split']=='test' and n>=self.settings.MIN_PERFORMANCE_SAMPLE:
                sample=next(r for r in result['records'] if r['strategy']==row['strategy'] and r['symbol']==row['symbol'])
                artifact.append(dict(strategy=row['strategy'],symbol=row['symbol'],trades=n,wins=row['wins'],losses=row['losses'],split='test',source='tick_replay',engine_version='BLACK_TORNADO_1.0',config_hash=sample['config_hash'],test_end_ts=result['split_boundaries']['test_end']))
        (out/'oos-performance.json').write_text(json.dumps(artifact,indent=2))
        if include_independent:
            for sid,records in result.get('independent_records',{}).items():
                sub={**result,'records':records,'report':report(records),'independent_records':{},
                     'setup_counts':{k:v for k,v in result['setup_counts'].items() if k.startswith(sid+'|')}}
                self.save(sub,out/sid,False)
        return out
