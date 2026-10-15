import json,time
import httpx,pytest
from app.config import Settings
from app.notifications.telegram import TelegramClient
from app.notifications.delivery_test import run_delivery_test

async def test_test_requires_explicit_authorization(tmp_path):
    with pytest.raises(ValueError): await run_delivery_test(Settings(),tmp_path/'out.json')

@pytest.mark.parametrize('admin',[True,False])
async def test_delivery_permission_and_two_labeled_messages(tmp_path,monkeypatch,admin):
    import app.notifications.delivery_test as module
    t=TelegramClient(Settings(TELEGRAM_BOT_TOKEN='TEST_TOKEN',TELEGRAM_CHAT_ID='-100123'))
    calls=[]
    def handler(req):
        method=req.url.path.split('/')[-1];body=json.loads(req.content);calls.append((method,body))
        data={'getMe':{'id':1,'username':'test_bot'},'getChat':{'id':-100123,'type':'channel'},'getChatMember':{'status':'administrator' if admin else 'member','can_post_messages':admin},'sendMessage':{'message_id':100+len(calls)}}[method]
        return httpx.Response(200,json={'ok':True,'result':data})
    await t._client.aclose();t._client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(module,'TelegramClient',lambda _:t)
    report=await run_delivery_test(t.settings,tmp_path/'out.json',True)
    sent=[b for m,b in calls if m=='sendMessage']
    assert report['success']==admin and len(sent)==(2 if admin else 0)
    if admin:
        assert all('DELIVERY TEST' in b['text'] and '#BTTEST' in b['text'] for b in sent)
        assert 'UNVERIFIED' in sent[1]['text'] and report['trades_created']==0

async def test_full_publication_settlement_pipeline_with_mock_transport(db,scored,candles,monkeypatch):
    # Synthetic fixture + mock Telegram: production reservation/send/settlement
    # path. The separate evidence file records the real external delivery test.
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    import app.services.scanner as module
    from app.services.scanner import SignalScanner
    from app.strategies.base import build_context
    from app.engine.scheduler import slot_for_entry
    from app.engine.global_signal_manager import GlobalSignalManager
    from app.engine.outcome_tracker import OutcomeTracker
    from app.engine.quote_buffer import QuoteBuffer
    cfg=db.settings.model_copy(update={'DRY_RUN':False,'TELEGRAM_BOT_TOKEN':'TEST_ONLY','TELEGRAM_CHAT_ID':'-100123'})
    tg=TelegramClient(cfg);messages=[]
    def handler(req):
        messages.append(json.loads(req.content));return httpx.Response(200,json={'ok':True,'result':{'message_id':len(messages)}})
    await tg._client.aclose();tg._client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    now=time.time();slot=slot_for_entry(int(now)+12,cfg)
    monkeypatch.setattr(module,'next_entry_slot',lambda *a:slot)
    ctx=build_context('EURUSD-OTC',now,candles,last_price=1)
    market=SimpleNamespace(last_flush=now,_pending_quotes=[],build_context=lambda *a:ctx)
    manager=GlobalSignalManager(db)
    scored.candidate.strategy='BT03';scored.candidate.details={'test_only':True,'strategy_name':'ADAPTIVE_PULLBACK'}
    scanner=SignalScanner(cfg,db,market,tg,manager,SimpleNamespace(schedule=lambda *a:None))
    scanner.rank_candidates=AsyncMock(return_value=[scored]);scanner.filter.apply=lambda *a:SimpleNamespace(passed=True)
    published=await scanner.scan_cycle(now)
    assert published and published.published
    assert (await db.get_signal(published.signal_id)).delivery_state=='sent'
    await db.insert_quote('EURUSD-OTC',slot.entry_ts,1.,received_ts=slot.entry_ts)
    await db.insert_quote('EURUSD-OTC',slot.expiry_ts,1.1,received_ts=slot.expiry_ts)
    tracker=OutcomeTracker(cfg,db,QuoteBuffer(),tg,manager)
    assert await tracker.settle(published.signal_id,now=slot.expiry_ts+1)
    assert not await tracker.settle(published.signal_id,now=slot.expiry_ts+2)
    record=await db.get_signal(published.signal_id)
    assert record.outcome=='WIN' and record.result_delivery_state=='sent'
    assert len(messages)==2 and '#BTTEST' in messages[0]['text'] and '✅ WIN' in messages[1]['text']
    assert not (await db.lock_state())['locked']
    assert (await db.aggregate_outcomes('bt_live'))['wins']==1
    await tg.close()
