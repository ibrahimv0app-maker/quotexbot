from types import SimpleNamespace
import httpx,pytest
from app.notifications.telegram import TelegramClient,esc
from app.config import Settings
from app.engine.outcome_tracker import OutcomeResult

def signal():
    return SimpleNamespace(signal_no=1,symbol='<S>',direction='CALL',entry_ts=600,expiry_ts=660,sent_ts=588,score=80,strategy='BT03',snapshot={'details':{'strategy_name':'ADAPTIVE_PULLBACK'}},reasons=[],filters_passed=[])

def test_escape(): assert esc('<>&')=='&lt;&gt;&amp;'

async def test_exact_requested_signal_format():
    t=TelegramClient(Settings());s=signal();s.symbol='EURUSD-OTC';s.score=82;s.entry_ts=25980;s.expiry_ts=26040
    assert t.format_signal(s)=='''╔══ 🌑 BLACK TORNADO ══╗
      🚨 SIGNAL DETECTED

PAIR: EURUSD-OTC
TRADE: 🟢 CALL
TIME: 12:13:00 PKT
EXP: 60 SECONDS
BT SCORE: 82/100
SETUP: PULLBACK RECLAIM

╚══════ #BT001 ══════╝'''
    await t.close()

async def test_format_escaping_and_missing_result():
    t=TelegramClient(Settings());assert '&lt;S&gt;' in t.format_signal(signal())
    r=t.format_result(signal(),OutcomeResult('UNVERIFIED','feed_estimated',None,None,None,None,'entry missing'))
    assert '❔ UNVERIFIED' in r and 'entry missing' in r and 'Feed-estimated' in r
    assert 'WIN' not in r
    await t.close()

@pytest.mark.parametrize('status,emoji',[('WIN','✅'),('LOSS','❌'),('DRAW','➖'),('UNVERIFIED','❔')])
async def test_result_status_and_matching_id(status,emoji):
    t=TelegramClient(Settings());r=t.format_result(signal(),OutcomeResult(status,'feed_estimated',None,None,None,None))
    assert f'{emoji} {status}' in r and '#BT001' in r and 'RESULT' in r and 'Feed-estimated' in r
    assert 'Win Rate' not in r and 'unavailable' not in r
    await t.close()

async def test_put_and_persistent_id_expansion():
    t=TelegramClient(Settings());s=signal();s.direction='PUT';s.strategy='BT07';s.signal_no=1007;s.snapshot={'details':{'strategy_name':'BREAKOUT_RETEST'}}
    r=t.format_signal(s)
    assert 'TRADE: 🔴 PUT' in r and 'SETUP: BREAKOUT RETEST' in r and '#BT1007' in r
    await t.close()

async def test_audit_real_counts_not_constants():
    t=TelegramClient(Settings(TELEGRAM_INCLUDE_AUDIT_DETAILS=True))
    r=t.format_result(signal(),OutcomeResult('WIN','feed_estimated',1.12345,600,1.12358,660),{'wins':18,'losses':7,'draws':1,'unverified':2})
    assert 'Wins: 18 | Losses: 7' in r and 'Win Rate: 72%' in r and '1.12345' in r and '1.12358' in r
    assert 'Draws: 1' in r and 'Unverified: 2' in r
    await t.close()

async def test_ambiguous_telegram_not_retried():
    t=TelegramClient(Settings(TELEGRAM_BOT_TOKEN='SECRET',TELEGRAM_CHAT_ID='x'));calls=[]
    def fail(req): calls.append(req);raise httpx.ReadTimeout('SECRET_URL')
    await t._client.aclose();t._client=httpx.AsyncClient(transport=httpx.MockTransport(fail))
    assert not await t.send('test') and len(calls)==1 and 'SECRET' not in t.last_error
    await t.close()
