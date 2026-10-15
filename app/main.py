"""Long-running HTTP service with managed background feed/scanner lifecycles."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
import asyncio, time, logging
from fastapi import FastAPI
from app.config import get_settings
from app.database.repository import Database
from app.services.market_service import MarketService
from app.services.scanner import SignalScanner
from app.engine.global_signal_manager import GlobalSignalManager
from app.engine.outcome_tracker import OutcomeTracker
from app.notifications.telegram import TelegramClient
from app.logging_setup import setup_logging, log
from app.api.health import router as health_router
from app.api.stats import router as stats_router

@asynccontextmanager
async def lifespan(app):
    cfg = get_settings()
    setup_logging(cfg.LOG_LEVEL,cfg.LOG_JSON)
    # HTTP libraries log full Telegram URLs at INFO; disable before first request.
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    db = Database(cfg)
    for attempt in range(6):
        try: await db.connect(); break
        except Exception as exc:
            log.warning('database.startup_retry',attempt=attempt,error_type=type(exc).__name__)
            if attempt == 5: raise RuntimeError('Database startup failed') from None
            await db.disconnect()
            await asyncio.sleep(min(2**attempt,15))
    manager = GlobalSignalManager(db)
    await manager.ensure_initialised()
    market,telegram = MarketService(cfg,db),TelegramClient(cfg)
    tracker = OutcomeTracker(cfg,db,market.quotes,telegram,manager)
    scanner = SignalScanner(cfg,db,market,telegram,manager,tracker)
    app.state.runtime = SimpleNamespace(settings=cfg,db=db,market=market,telegram=telegram,
        manager=manager,tracker=tracker,scanner=scanner,started=time.time())
    # Read persisted history before streams start; repaired REST history follows
    # asynchronously on every connection establishment, never blocking health startup.
    for symbol in cfg.SYMBOLS: await market.candles.load_from_db(symbol)
    await market.start()
    await tracker.resume_pending()
    await scanner.start()
    log.info('service.started',dry_run=cfg.DRY_RUN,symbols=len(cfg.SYMBOLS))
    try: yield
    finally:
        await scanner.stop()
        await tracker.stop()
        await market.stop()
        await telegram.close()
        await db.disconnect()

app = FastAPI(title='BLACK TORNADO M1 Signal Monitor',version='1.0.0',lifespan=lifespan)
app.include_router(health_router)
app.include_router(stats_router)

@app.get('/')
def root():
    return dict(service='BLACK TORNADO v1.0 signal-only bot',health='/health',feeds='/health/feeds',stats='/stats')

if __name__ == '__main__':
    import uvicorn
    cfg = get_settings()
    uvicorn.run('app.main:app',host='0.0.0.0',port=cfg.PORT,workers=1,log_level=cfg.LOG_LEVEL.lower())
