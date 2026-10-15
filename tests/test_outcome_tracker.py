import time,pytest
from app.engine.outcome_tracker import evaluate_direction,OutcomeTracker
from app.engine.quote_buffer import QuoteBuffer
from app.engine.global_signal_manager import GlobalSignalManager
from app.notifications.telegram import TelegramClient
@pytest.mark.parametrize('d,a,b,want',[('CALL',1,2,'WIN'),('PUT',1,2,'LOSS'),('PUT',2,1,'WIN'),('CALL',2,1,'LOSS'),('CALL',1,1,'DRAW')])
def test_price_compare(d,a,b,want): assert evaluate_direction(d,a,b)==want
def test_no_future_entry():
    q=QuoteBuffer();q.add('S',101,99,101);q.add('S',99,1,99)
    assert q.at_or_before('S',100,2)==(99,1)
    assert q.at_or_before('S',98,2) is None
async def test_db_no_future_quote(db):
    await db.insert_quote('S',99,1);await db.insert_quote('S',101,99)
    assert (await db.find_quote('S',100,8)).price==1
async def test_unverified_timeout_releases(db):
    now=int(time.time());sid='outcome-test'
    await db.create_signal(id=sid,signal_no=1,symbol='EURUSD-OTC',direction='CALL',strategy='test',
        entry_ts=now-300,expiry_ts=now-240,status='active')
    await db.acquire_lock(sid)
    tg=TelegramClient(db.settings)
    tracker=OutcomeTracker(db.settings,db,QuoteBuffer(),tg,GlobalSignalManager(db))
    assert await tracker.settle(sid,now)
    sig=await db.get_signal(sid)
    assert sig.outcome=='UNVERIFIED' and 'entry' in sig.outcome_note
    assert not (await db.lock_state())['locked']
    await tg.close()
async def test_persisted_quote_result(db):
    now=int(time.time());sid='quote-test';entry=now-70;expiry=now-10
    await db.create_signal(id=sid,signal_no=1,symbol='S',direction='CALL',strategy='test',entry_ts=entry,expiry_ts=expiry,status='active')
    await db.acquire_lock(sid)
    await db.insert_quote('S',entry,1,received_ts=entry);await db.insert_quote('S',expiry,2,received_ts=expiry)
    tg=TelegramClient(db.settings);tracker=OutcomeTracker(db.settings,db,QuoteBuffer(),tg,GlobalSignalManager(db))
    assert await tracker.settle(sid,now)
    assert (await db.get_signal(sid)).outcome=='WIN'
    await tg.close()
