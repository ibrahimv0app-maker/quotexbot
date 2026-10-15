import asyncio,time,json,pytest,httpx
from app.feed.client import FeedClient,SymbolUnavailable,FeedError
from app.feed.websocket_manager import StreamManager,ConnectionState
from app.feed.symbol_registry import SymbolRegistry
from app.config import Settings

async def test_unknown_symbol_no_invention():
    c=FeedClient('https://test.invalid',max_retries=1)
    await c._client.aclose()
    c._client=httpx.AsyncClient(base_url='https://test.invalid',transport=httpx.MockTransport(lambda r:httpx.Response(400,json={'error':'Unknown symbol'})))
    with pytest.raises(SymbolUnavailable): await c.get_candles('FAKE')
    await c.aclose()
async def test_bad_payload():
    c=FeedClient('https://test.invalid',max_retries=1)
    await c._client.aclose()
    c._client=httpx.AsyncClient(base_url='https://test.invalid',transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'oops':[]})))
    with pytest.raises(FeedError): await c.get_candles('S')
    await c.aclose()
def test_malformed_stream_does_not_call_tick():
    got=[];m=StreamManager(Settings(SYMBOLS=['EURUSD-OTC']),SymbolRegistry(['EURUSD-OTC']),lambda *a:got.append(a))
    st=ConnectionState(0,['EURUSD-OTC'],'ws')
    for raw in ['notjson','[]','{}','{"price":"bad"}']: m._handle_raw(raw,st)
    assert not got
async def test_reconnect_fallback_and_unaffected_groups():
    cfg=Settings(SYMBOLS=['EURUSD-OTC'])
    m=StreamManager(cfg,SymbolRegistry(cfg.SYMBOLS),lambda *a:None)
    state=ConnectionState(0,cfg.SYMBOLS,'ws')
    attempts=[]
    async def fail(st): attempts.append(st.transport);raise RuntimeError('disconnect')
    async def sse(st): attempts.append(st.transport);m._stop.set()
    m._run_ws=fail;m._run_sse=sse
    # Avoid real reconnect delays in this isolated unit test.
    import app.feed.websocket_manager as module
    original=module.asyncio.sleep
    async def immediate(*a): await original(0)
    from unittest.mock import patch
    with patch.object(module.asyncio,'sleep',immediate): await m._run_connection(state)
    assert attempts==['ws','ws','ws','sse']
