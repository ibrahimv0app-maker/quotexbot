import secrets
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import update
from app.database.models import SystemControl
router = APIRouter()

@router.get('/stats')
async def stats(request: Request):
    rt = request.app.state.runtime
    return dict(outcomes=await rt.db.aggregate_outcomes(),black_tornado_outcomes=await rt.db.aggregate_outcomes("bt_paper" if rt.settings.DRY_RUN else "bt_live"),scanner=rt.scanner.status(),
        persisted_rejections=await rt.db.rejected_reasons(),lock=await rt.db.lock_state(),telegram=dict(sent=rt.telegram.sent,failed=rt.telegram.failed,
        last_error=rt.telegram.last_error),recent=await rt.db.recent_signals())

@router.get('/stats/strategies')
async def strategies(request: Request):
    return dict(statistics=await request.app.state.runtime.db.strategy_stats(),
        note='Feed-estimated forward paper/live records; these are NOT validated OOS ranking inputs.')

@router.post('/admin/pause/{paused}')
async def pause(paused: bool, request: Request):
    rt = request.app.state.runtime
    key = rt.settings.ADMIN_API_KEY
    supplied = request.headers.get('Authorization','').removeprefix('Bearer ')
    if not key or not secrets.compare_digest(key,supplied): raise HTTPException(403,'Forbidden')
    async with rt.db.session() as s, s.begin():
        await s.execute(update(SystemControl).where(SystemControl.id==1).values(paused=paused))
    rt.scanner.paused = paused or rt.settings.KILL_SWITCH
    await rt.db.log_event('info','kill_switch',str(paused))
    return dict(paused=rt.scanner.paused,existing_outcomes_continue=True)
