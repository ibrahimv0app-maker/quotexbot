"""Liveness and feed readiness are separate: outages must not cause restart loops."""
import time
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
router = APIRouter()

@router.get('/health')
async def health(request: Request):
    rt = request.app.state.runtime
    db_ok = False
    try:
        async with rt.db.session() as s: await s.execute(text('SELECT 1'))
        db_ok = True
    except Exception: pass
    scanner_ok = rt.scanner.task is not None and not rt.scanner.task.done() and time.time()-rt.scanner.last_cycle_ts < 30
    data = dict(status='ok' if db_ok and scanner_ok else 'degraded',database=db_ok,
        scanner_alive=scanner_ok,mode='paper' if rt.settings.DRY_RUN else 'signal_only',
        uptime_seconds=round(time.time()-rt.started,1),feed_ready=rt.market.registry.summary()['healthy'])
    return JSONResponse(data,status_code=200 if db_ok and scanner_ok else 503)

@router.get('/health/feeds')
async def feeds(request: Request):
    rt = request.app.state.runtime
    return dict(**rt.market.status(),pairs=rt.market.registry.snapshot())
