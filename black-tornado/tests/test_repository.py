import time
async def test_chunked_candles_and_nullable_volume(db):
    base=(int(time.time())//60-500)*60
    rows=[dict(symbol='S',time=base+i*60,interval='1m',open=1,high=2,low=.5,close=1,volume=None,source='stream') for i in range(300)]
    assert await db.upsert_candles(rows)==300
    rows[-1]['close']=1.5
    await db.upsert_candles(rows[-1:])
    stored=await db.load_candles('S',400)
    assert len(stored)==300 and stored[-1].close==1.5 and stored[-1].volume is None

async def test_receipt_time_prevents_future_entry(db):
    await db.insert_quote('S',99,1,received_ts=99)
    await db.insert_quote('S',100,999,received_ts=101)
    q=await db.find_quote('S',100,8,received_by=100)
    assert q.price==1

async def test_bt_statistics_isolate_live_paper_legacy_and_unsent(db,scored,monkeypatch):
    from sqlalchemy import update
    from app.database.models import Signal
    from app.engine.global_signal_manager import GlobalSignalManager
    from app.engine.scheduler import slot_for_entry
    m=GlobalSignalManager(db);now=int(time.time())
    for idx,(strategy,state,outcome,notified) in enumerate([('BT01','paper','WIN',False),('BT02','sent','LOSS',True),('old_strategy','sent','WIN',True),('BT02','sending','WIN',False),('BT_FAKE','sent','WIN',True)]):
        from types import SimpleNamespace
        import app.engine.global_signal_manager as gm
        monkeypatch.setattr(gm,'time',SimpleNamespace(time=lambda:now+idx*120))
        scored.candidate.strategy=strategy
        r=await m.publish(slot_for_entry(now+12+idx*120,db.settings),scored,{},now+idx*120,1)
        async with db.session() as s,s.begin():
            await s.execute(update(Signal).where(Signal.id==r.signal_id).values(delivery_state=state,notified=notified))
        await m.resolve(r.signal_id,outcome)
    paper=await db.aggregate_outcomes('bt_paper');live=await db.aggregate_outcomes('bt_live')
    assert paper['wins']==1 and paper['losses']==0 and paper['signals_delivered']==0
    assert live['wins']==0 and live['losses']==1 and live['signals_delivered']==1
