import pytest
from app.config import Settings
from app.engine.scheduler import next_entry_slot,slot_for_entry,format_local
@pytest.mark.parametrize('lead',[10,12,15])
def test_window(lead):
    s=slot_for_entry(600,Settings(SIGNAL_LEAD_SECONDS=lead))
    assert s.send_from==585 and s.send_until==590
    assert s.expiry_ts==660
    assert s.contains(588) and not s.contains(591)
def test_next_boundary(): assert next_entry_slot(588,Settings()).entry_ts==600
def test_pkt(): assert format_local(0,'Asia/Karachi')=='05:00:00 PKT'
