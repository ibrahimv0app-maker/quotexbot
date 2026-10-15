import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from app.services.scanner import SignalScanner
from app.config import Settings
from app.strategies.base import build_context
from app.feed.symbol_registry import SymbolRegistry
from app.database.models import SystemControl

async def test_all_pairs_ranked_even_when_paused(db,candles):
    cfg=db.settings
    registry=SymbolRegistry(['A','B'])
    called=[]
    def context(sym,now):
        called.append(sym)
        return build_context(sym,now,candles,last_price=candles[-1].close,data_age=0)
    market=SimpleNamespace(registry=registry,build_context=context)
    scanner=SignalScanner(cfg,db,market,None,None)
    async with db.session() as s,s.begin():
        row=await s.get(SystemControl,1);row.paused=True
    await scanner.scan_cycle()
    assert called==['A','B'] and scanner.paused and scanner.scanned_pairs==2

async def test_no_telegram_when_paper(db,scored,candles,monkeypatch):
    # Exercise the real persistent reservation, not a mock lock.
    import app.services.scanner as module
    from app.engine.scheduler import slot_for_entry
    from app.engine.global_signal_manager import GlobalSignalManager
    cfg=db.settings
    now=time.time();slot=slot_for_entry(int(now)+12,cfg)
    monkeypatch.setattr(module,'next_entry_slot',lambda *a:slot)
    ctx=build_context('EURUSD-OTC',now,candles,last_price=1)
    market=SimpleNamespace(last_flush=now,_pending_quotes=[],build_context=lambda *a:ctx,
        quotes=SimpleNamespace(last_ts=lambda s:now))
    telegram=SimpleNamespace(send_signal=AsyncMock())
    tracker=SimpleNamespace(schedule=lambda *a:None)
    scanner=SignalScanner(cfg,db,market,telegram,GlobalSignalManager(db),tracker)
    scanner.rank_candidates=AsyncMock(return_value=[scored])
    scanner.filter.apply=lambda *a:SimpleNamespace(passed=True)
    # target is slot.entry-12; int(now) target is already eligible.
    result=await scanner.scan_cycle(now)
    assert result and result.published
    telegram.send_signal.assert_not_called()
    assert (await db.get_active_signal()).delivery_state=='paper'
