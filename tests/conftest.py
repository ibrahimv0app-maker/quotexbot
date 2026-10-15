import os,time,pytest
from app.config import Settings
from app.database.repository import Database
from app.database.models import Base
from app.feed.client import Candle
from app.strategies.base import Candidate,build_context
from app.engine.candidate_scorer import ScoredCandidate

@pytest.fixture(params=['sqlite','postgres'])
async def db(request,tmp_path):
    if request.param=='postgres':
        url = os.environ.get('TEST_POSTGRES_URL')
        if not url: pytest.skip('Set TEST_POSTGRES_URL for real PostgreSQL integration')
    else: url = f'sqlite+aiosqlite:///{tmp_path}/test.db'
    cfg = Settings(DATABASE_URL=url)
    database = Database(cfg)
    await database.connect()
    await database.ensure_lock_row()
    yield database
    async with database._engine.begin() as c: await c.run_sync(Base.metadata.drop_all)
    await database.disconnect()

@pytest.fixture
def candles():
    start = (int(time.time())//60-160)*60
    return [Candle(start+i*60,1+i*.0001,1+i*.0001+.00012,1+i*.0001-.00008,1+i*.0001+.00007,0) for i in range(150)]

@pytest.fixture
def scored():
    return ScoredCandidate(Candidate('EURUSD-OTC','trend_pullback','CALL',.9,['unit test'],['fresh data']),82,{'setup':23})

@pytest.fixture(autouse=True)
def no_real_telegram_credentials_in_unit_tests(monkeypatch):
    # Even a developer's private .env must never cause test fixtures to post.
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','')
    monkeypatch.setenv('TELEGRAM_CHAT_ID','')
