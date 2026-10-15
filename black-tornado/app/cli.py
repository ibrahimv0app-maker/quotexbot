"""Diagnostics, capture, exports and replay. Run: python -m app.cli --help."""
from __future__ import annotations
import argparse, asyncio, json, time, logging, math
from pathlib import Path
from app.config import Settings
from app.feed.client import FeedClient, parse_candles
from app.feed.symbol_registry import SymbolRegistry
from app.feed.websocket_manager import StreamManager

async def diagnose(args):
    cfg = Settings()
    symbols = cfg.SYMBOLS if args.all else [args.symbol]
    client = FeedClient(cfg.API_BASE_URL)
    results = await client.get_candles_many(symbols,limit=args.limit,concurrency=cfg.CANDLE_FETCH_CONCURRENCY)
    registry = SymbolRegistry(symbols)
    ticks = []
    def tick(sym,price,ts,volume):
        canonical = registry.normalise(sym)
        if canonical and math.isfinite(price) and price>0 and abs(time.time()-ts)<30:
            ticks.append(dict(symbol=canonical,raw_symbol=sym,price=price,ts=ts,received_ts=time.time(),source='stream'))
    manager = StreamManager(cfg,registry,tick)
    await manager.start()
    await asyncio.sleep(args.seconds)
    status = manager.status()
    await manager.stop()
    pairs = []
    for sym,(cs,err,ms) in results.items():
        ts = [c.time for c in cs]
        live = [t for t in ticks if t['symbol']==sym]
        pairs.append(dict(symbol=sym,history_count=len(cs),error=err,rest_ms=ms,
            gaps=sum(ts[i]-ts[i-1]!=60 for i in range(1,len(ts))),first=ts[0] if ts else None,
            last=ts[-1] if ts else None,tick_count=len(live),last_tick=live[-1] if live else None,
            median_latency_seconds=sorted(t['received_ts']-t['ts'] for t in live)[len(live)//2] if live else None))
    report = dict(captured_at=time.time(),pairs=pairs,stream=status,
        note='Empty candles do not imply a server 500. Availability is observational, not permanent.')
    out = Path(args.output);out.mkdir(parents=True,exist_ok=True)
    (out/'diagnostic.json').write_text(json.dumps(report,indent=2))
    candles = {s:[c.as_dict() for c in cs if c.close_time<=time.time()] for s,(cs,err,ms) in results.items()}
    (out/'candles.json').write_text(json.dumps(candles))
    (out/'quotes.jsonl').write_text(''.join(json.dumps(t)+'\n' for t in ticks))
    print(json.dumps(report,indent=2))
    await client.aclose()

def backtest(args):
    from app.backtesting.engine import Backtester
    cfg = Settings()
    raw = json.loads(Path(args.candles).read_text())
    candles = {s:parse_candles(dict(symbol=s,candles=rows),s) for s,rows in raw.items()}
    quotes = [json.loads(line) for line in Path(args.quotes).read_text().splitlines()] if args.quotes else []
    bt = Backtester(cfg)
    result = bt.run(candles,quotes,strategy=args.strategy)
    bt.save(result,args.output)
    print(json.dumps(result['report'],indent=2))
    print('mode:',result['mode'],'setups:',sum(result['setup_counts'].values()))

async def export(args):
    from app.database.repository import Database
    from app.database.models import Candle as DBCandle, QuoteObservation, Signal
    from sqlalchemy import select
    db = Database(Settings()); await db.connect()
    out = Path(args.output);out.mkdir(parents=True,exist_ok=True)
    candles = {}
    async with db.session() as s:
        for c in (await s.execute(select(DBCandle).order_by(DBCandle.time))).scalars():
            candles.setdefault(c.symbol,[]).append(dict(time=c.time,open=c.open,high=c.high,low=c.low,close=c.close,volume=c.volume))
        quotes = (await s.execute(select(QuoteObservation).order_by(QuoteObservation.ts))).scalars().all()
        (out/'quotes.jsonl').write_text(''.join(json.dumps(dict(symbol=q.symbol,ts=q.ts,price=q.price,received_ts=q.received_ts))+'\n' for q in quotes))
    (out/'candles.json').write_text(json.dumps(candles))
    async with db.session() as s:
        signals = (await s.execute(select(Signal).order_by(Signal.entry_ts))).scalars().all()
        raw = [{col.name:getattr(sig,col.name) for col in Signal.__table__.columns} for sig in signals]
    (out/'signals.json').write_text(json.dumps(raw,indent=2,default=str))
    await db.disconnect()
    print('Exported',out)

async def manual(args):
    from app.database.repository import Database
    db = Database(Settings()); await db.connect()
    sig = await db.get_signal(args.id)
    if not sig: raise ValueError('Signal ID not found')
    await db.update_signal(sig.id,manual_outcome=args.outcome,manual_note=args.note)
    await db.log_event('info','manual_confirmation',sig.id+':'+args.outcome)
    await db.disconnect()
    print('Stored manual confirmation separately; feed outcome unchanged.')

def main():
    logging.getLogger('httpx').setLevel(logging.WARNING)
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command',required=True)
    d = sub.add_parser('diagnose');d.add_argument('--symbol',default='EURUSD-OTC');d.add_argument('--all',action='store_true')
    d.add_argument('--seconds',type=int,default=15);d.add_argument('--limit',type=int,default=2001);d.add_argument('--output',default='data/capture')
    b = sub.add_parser('backtest');b.add_argument('--candles',required=True);b.add_argument('--quotes');b.add_argument('--strategy');b.add_argument('--output',default='reports/backtest')
    e = sub.add_parser('export');e.add_argument('--output',default='data/export')
    m = sub.add_parser('manual-confirm');m.add_argument('--id',required=True)
    m.add_argument('--outcome',required=True,choices=['WIN','LOSS','DRAW']);m.add_argument('--note',required=True)
    v=sub.add_parser('validate');v.add_argument('--candles',required=True);v.add_argument('--quotes');v.add_argument('--output',default='reports/validation')
    tg=sub.add_parser('telegram-test');tg.add_argument('--send',action='store_true');tg.add_argument('--output',default='evidence/telegram-delivery-test.json')
    args = p.parse_args()
    if args.command=='telegram-test':
        from app.notifications.delivery_test import run_delivery_test
        result=asyncio.run(run_delivery_test(Settings(),args.output,args.send))
        print(json.dumps(result,indent=2))
        if not result['success']: raise SystemExit(1)
        return
    if args.command=='validate':
        from app.backtesting.validation import run_validation
        from app.feed.client import parse_candles
        raw=json.loads(Path(args.candles).read_text());bars={s:parse_candles(dict(symbol=s,candles=cs),s) for s,cs in raw.items()}
        quotes=[json.loads(l) for l in Path(args.quotes).read_text().splitlines()] if args.quotes else []
        result=run_validation(Settings(),bars,quotes)
        Path(args.output).mkdir(parents=True,exist_ok=True);Path(args.output,'validation.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2))
    elif args.command=='backtest': backtest(args)
    else: asyncio.run(diagnose(args) if args.command=='diagnose' else manual(args) if args.command=='manual-confirm' else export(args))

if __name__=='__main__': main()
