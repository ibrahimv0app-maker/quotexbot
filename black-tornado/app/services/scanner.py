"""Fixed-cadence all-pair scanning; only the best qualified setup is published."""
from __future__ import annotations
import asyncio, time, json
from pathlib import Path
from collections import Counter
from app.engine.candidate_scorer import CandidateScorer
from app.engine.regime_filter import RegimeFilter
from app.engine.scheduler import next_entry_slot
from app.strategies.registry import make_strategies
from app.logging_setup import log, log_throttled

def resolve_conflicts(scored):
    # Opposite qualified strategies on THE SAME pair are unresolved -> discard
    # that pair. Opposite directions on independent pairs are not a conflict.
    sides = {}
    for s in scored:
        sides.setdefault(s.candidate.symbol,set()).add(s.candidate.direction)
    ranked=sorted((s for s in scored if len(sides[s.candidate.symbol])==1),
        key=lambda s:(-s.score,s.candidate.symbol,s.candidate.strategy))
    # Collapse correlated modules expressing the same structural opportunity.
    unique={}
    for s in ranked:
        key=(s.candidate.symbol,s.candidate.direction,s.candidate.details.get('setup_family',s.candidate.strategy))
        unique.setdefault(key,s)
    return list(unique.values())

class SignalScanner:
    def __init__(self,settings,db,market,telegram,manager,tracker=None):
        self.settings,self.db,self.market,self.telegram,self.manager = settings,db,market,telegram,manager
        self.tracker = tracker
        self.filter,self.scorer = RegimeFilter(settings),CandidateScorer(settings)
        self.strategies = make_strategies(settings)
        from app.black_tornado.core import BlackTornado
        self.bt_engine = self.strategies[0].engine if self.strategies else BlackTornado(settings)
        self.cycles,self.scanned_pairs,self.candidates_seen,self.signals_sent = 0,0,0,0
        self.rejections = Counter()
        self.recent = []
        self.task = None
        self.paused = settings.KILL_SWITCH
        self.last_cycle_ts = 0
        self.cycle_ms = 0
        self.overruns = 0
        self._last_diagnostic = 0
        self._last_entry = 0
        self.performance = {}
        if settings.OOS_PERFORMANCE_FILE:
            rows = json.loads(Path(settings.OOS_PERFORMANCE_FILE).read_text())
            if any(not r.get('test_end_ts') or r['test_end_ts'] >= time.time() for r in rows):
                raise ValueError('OOS artifact requires a completed historical test_end_ts')
            self.performance = {(r['strategy'],r['symbol']):r for r in rows}
    async def start(self): self.task = asyncio.create_task(self._loop())
    async def stop(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task,return_exceptions=True)
    async def _loop(self):
        while True:
            start = time.monotonic()
            try: await self.scan_cycle()
            except asyncio.CancelledError: raise
            except Exception as e: log_throttled('scanner','scanner.error',error_type=type(e).__name__)
            elapsed = time.monotonic()-start
            self.cycle_ms = round(elapsed*1000,2)
            if elapsed>self.settings.SCAN_INTERVAL_SECONDS: self.overruns += 1
            await asyncio.sleep(max(0,self.settings.SCAN_INTERVAL_SECONDS-elapsed))
    def _rank(self,contexts,now):
        ranked,diag = [],[]
        rejects = Counter()
        for ctx in contexts:
            bt=self.bt_engine.analyze(ctx)
            for strategy in self.strategies:
                assessment=strategy.assess(bt)
                cand = assessment.candidate
                if cand is None:
                    rejects[strategy.strategy_id+': '+assessment.rejection] += 1
                    continue
                f = self.filter.apply(ctx,cand)
                reason = f.rejection if not f.passed else None
                score,parts = 0,{}
                if f.passed:
                    cand.filters_passed = f.filters_passed
                    s = self.scorer.score(ctx,cand,self.performance.get((cand.strategy,cand.symbol)))
                    score,parts = s.score,s.components
                    if s.score >= self.settings.MIN_SETUP_SCORE: ranked.append(s)
                    else: reason = 'below_score_threshold'
                if reason: rejects[reason] += 1
                diag.append(dict(cycle_ts=int(now),symbol=ctx.symbol,strategy=strategy.strategy_id,
                    direction=cand.direction,score=score,components=parts,rejected_reason=reason))
        return resolve_conflicts(ranked),diag,rejects
    async def rank_candidates(self,now):
        contexts = [self.market.build_context(sym,now) for sym in self.market.registry.symbols]
        contexts = [ctx for ctx in contexts if ctx is not None]
        self.scanned_pairs = len(contexts)
        ranked,diag,rejects = await asyncio.to_thread(self._rank,contexts,now)
        self.rejections.update(rejects)
        self.candidates_seen += len(diag)
        if now-self._last_diagnostic >= 60:
            if diag: await self.db.record_candidates_bulk(diag)
            self._last_diagnostic = now
        self.recent = [s.to_dict() for s in ranked[:5]]
        return ranked
    async def scan_cycle(self,now=None):
        now = time.time() if now is None else now
        self.cycles += 1
        self.last_cycle_ts = now
        # Analyse even while paused or while an outcome is unresolved.
        from app.database.models import SystemControl
        async with self.db.session() as session:
            control = await session.get(SystemControl, 1)
        self.paused = self.settings.KILL_SWITCH or bool(control and control.paused)
        ranked = await self.rank_candidates(time.time())
        clock = time.time()
        slot = next_entry_slot(clock,self.settings)
        target = slot.entry_ts-self.settings.SIGNAL_LEAD_SECONDS
        if self.paused or not ranked or not slot.contains(clock) or clock < target: return
        if self._last_entry == slot.entry_ts or await self.manager.is_busy(): return
        if clock-self.market.last_flush > 5 or len(self.market._pending_quotes)>5000:
            self.rejections['database_not_current'] += 1
            return
        best = ranked[0]
        ctx = self.market.build_context(best.candidate.symbol,clock)
        # Re-check freshness after compute and DB latency, no stale candidate delivery.
        if not ctx or not self.filter.apply(ctx,best.candidate).passed: return
        result = await self.manager.publish(slot,best,dict(details=best.candidate.details,
            volatility=best.candidate.details.get('volatility','Unknown'),atr_pct=ctx.atr_pct,data_age=ctx.data_age,
            last_source_timestamp=best.candidate.details.get('bt',{}).get('features',{}).get('live_source_ts'),
            candles=[c.as_dict() for c in ctx.candles[-self.bt_engine.config.lookback:]],score_notes=best.performance_note),best.candidate.details.get('bt',{}).get('decision_ts',clock),best.candidate.details.get('bt',{}).get('features',{}).get('live_price',ctx.price))
        if not result.published: return
        self._last_entry = slot.entry_ts
        # Always monitor reserved lifecycles, including ambiguous/failed Telegram sends.
        self.tracker.schedule(result.signal_id,ctx.symbol,best.candidate.direction,slot.entry_ts,slot.expiry_ts)
        if not await self.manager.claim_delivery(result.signal_id): return
        signal = await self.db.get_signal(result.signal_id)
        if self.settings.DRY_RUN:
            await self.db.update_signal(signal.id,delivery_state='paper')
            log.info('paper.signal',signal_no=signal.signal_no,pair=signal.symbol,score=round(signal.score,2))
        else:
            # Final clock fence after reserving/claiming. No retry if delivery is ambiguous.
            if not slot.contains(time.time()):
                await self.db.update_signal(signal.id,delivery_state='missed_window')
                return
            await self.db.update_signal(signal.id,sent_ts=int(time.time()))
            signal = await self.db.get_signal(signal.id)
            ok = await self.telegram.send_signal(signal,deadline=slot.send_until)
            await self.db.update_signal(signal.id,snapshot={**signal.snapshot,'notification_ack_latency_ms':self.telegram.last_latency_ms})
            await self.manager.mark_notified(signal.id,ok,'' if ok else self.telegram.last_error)
            if ok: self.signals_sent += 1
        return result
    def status(self):
        return dict(cycles=self.cycles,scanned_pairs=self.scanned_pairs,candidates_seen=self.candidates_seen,
            signals_sent=self.signals_sent,kill_switch=self.paused,rejections=dict(self.rejections),
            recent=self.recent,last_cycle_ts=self.last_cycle_ts,cycle_ms=self.cycle_ms,overruns=self.overruns)
