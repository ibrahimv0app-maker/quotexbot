import asyncio,time,pytest
from app.engine.global_signal_manager import GlobalSignalManager
from app.engine.scheduler import slot_for_entry

def slot(): return slot_for_entry(int(time.time())+12,__import__('app.config',fromlist=['Settings']).Settings())
async def test_competing_reservations(db,scored):
    a,b=GlobalSignalManager(db),GlobalSignalManager(db)
    s=slot()
    r=await asyncio.gather(a.publish(s,scored,{},time.time(),1),b.publish(s,scored,{},time.time(),1))
    assert sum(x.published for x in r)==1
    assert await db.count_signals()==1
async def test_unique_entry_after_resolution(db,scored):
    m=GlobalSignalManager(db);s=slot()
    a=await m.publish(s,scored,{},time.time(),1)
    await m.resolve(a.signal_id,'WIN')
    assert not (await m.publish(s,scored,{},time.time(),1)).published
async def test_settle_once(db,scored):
    m=GlobalSignalManager(db);s=slot()
    a=await m.publish(s,scored,{},time.time(),1)
    assert await m.resolve(a.signal_id,'LOSS')
    assert not await m.resolve(a.signal_id,'WIN')
    assert (await db.strategy_stats())[0]['losses']==1
    assert not (await db.lock_state())['locked']
async def test_notify_claim_once(db,scored):
    m=GlobalSignalManager(db);r=await m.publish(slot(),scored,{},time.time(),1)
    assert await m.claim_delivery(r.signal_id)
    assert not await m.claim_delivery(r.signal_id)
async def test_missed_window(db,scored):
    m=GlobalSignalManager(db)
    s=slot_for_entry(int(time.time())-20,db.settings)
    assert not (await m.publish(s,scored,{},time.time(),1)).published
