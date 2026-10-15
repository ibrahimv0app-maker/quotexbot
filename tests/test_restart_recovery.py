import time
from app.database.repository import Database
from app.engine.global_signal_manager import GlobalSignalManager
from app.engine.scheduler import slot_for_entry
async def test_second_connection_recovers_lock(db,scored):
    m=GlobalSignalManager(db)
    r=await m.publish(slot_for_entry(int(time.time())+12,db.settings),scored,{},time.time(),1)
    other=Database(db.settings);await other.connect()
    try:
        assert await GlobalSignalManager(other).is_busy()
        sig=await other.get_active_signal()
        assert sig.id==r.signal_id
        assert await m.claim_delivery(sig.id)
        assert not await GlobalSignalManager(other).claim_delivery(sig.id)
    finally: await other.disconnect()
