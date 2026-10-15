"""Telegram notification client - HTML parse mode with strict escaping."""
from __future__ import annotations

import html
import time
from typing import Optional, TYPE_CHECKING

import httpx

from app.config import Settings
if TYPE_CHECKING:
    from app.engine.outcome_tracker import OutcomeResult
from app.logging_setup import log_throttled


def esc(text) -> str:
    """Escape text for Telegram HTML parse mode."""
    if text is None:
        return ""
    return html.escape(str(text), quote=False)


class TelegramClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0))
        self.last_latency_ms = None
        self.last_message_id = None
        self.sent = 0
        self.failed = 0
        self.last_error: Optional[str] = None

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    async def close(self) -> None:
        await self._client.aclose()

    async def send(self, text: str, disable_notification: bool = False, deadline=None) -> bool:
        if not self.configured:
            self.last_error = "telegram not configured"
            return False
        if deadline is not None and time.time() > deadline:
            self.last_error = "notification window missed"
            return False
        # Telegram offers no client idempotency key. A timeout may mean accepted;
        # never retry a financial alert with an uncertain delivery status.
        started=time.monotonic()
        try:
            resp = await self._client.post(f"https://api.telegram.org/bot{self.token}/sendMessage", json={
                "chat_id":self.chat_id,"text":text,"parse_mode":"HTML",
                "disable_web_page_preview":True,"disable_notification":disable_notification},
                timeout=min(20.0,max(.05,deadline-time.time())) if deadline is not None else 20.0)
            self.last_latency_ms=round((time.monotonic()-started)*1000,2)
            body = resp.json()
            if resp.status_code == 200 and body.get("ok"):
                self.last_message_id = body.get("result",{}).get("message_id")
                self.sent += 1
                self.last_error = None
                return True
            self.last_error = "Telegram rejected message; HTTP " + str(resp.status_code)
        except Exception as exc:
            self.last_latency_ms=round((time.monotonic()-started)*1000,2)
            # Never include exception URLs: they contain the bot credential.
            self.last_error = "Telegram delivery uncertain: " + type(exc).__name__
        self.failed += 1
        log_throttled("telegram", "telegram.notification_failure", error=self.last_error)
        return False

    # Boxed operator-requested layout. Extra audit fields are opt-in.
    def _details(self, signal):
        return (signal.snapshot or {}).get('details',{})

    def _tag(self, signal):
        return 'BTTEST' if self._details(signal).get('test_only') else f'BT{signal.signal_no:03d}'

    def format_signal(self,signal,scored_components=None):
        from app.engine.scheduler import format_local
        d=self._details(signal)
        setup='PULLBACK RECLAIM' if signal.strategy=='BT03' else d.get('strategy_name',signal.strategy).replace('_',' ').upper()
        lines=[]
        if d.get('test_only'): lines.append('🧪 DELIVERY TEST — NOT A LIVE SIGNAL\n')
        lines += ['╔══ 🌑 BLACK TORNADO ══╗','      🚨 SIGNAL DETECTED','',
            f'PAIR: {esc(signal.symbol)}',
            f"TRADE: {'🟢' if signal.direction=='CALL' else '🔴'} {esc(signal.direction)}",
            f'TIME: {format_local(signal.entry_ts,self.settings.DISPLAY_TIMEZONE)}',
            f'EXP: {signal.expiry_ts-signal.entry_ts:.0f} SECONDS',
            f'BT SCORE: {signal.score:.0f}/100',f'SETUP: {esc(setup)}']
        if self.settings.TELEGRAM_INCLUDE_AUDIT_DETAILS:
            bt=d.get('bt',{})
            lines += [f'Strategy: {esc(signal.strategy)}',
                f'BT confidence: {bt.get("BT_CONFIDENCE",0):.0f}/100; consistency, not win probability',
                'Manual entry only. Score is not a guaranteed probability.']
        lines += ['',f'╚══════ #{self._tag(signal)} ══════╝']
        return '\n'.join(lines)

    def format_result(self,signal,result,stats=None):
        stats=stats or {}
        d=self._details(signal)
        icon={'WIN':'✅','LOSS':'❌','DRAW':'➖','UNVERIFIED':'❔'}[result.outcome]
        lines=[]
        if d.get('test_only'): lines.append('🧪 DELIVERY TEST — NOT A TRADE RESULT\n')
        lines += ['╔══ 🌑 BLACK TORNADO ══╗','          RESULT','',
            f'PAIR: {esc(signal.symbol)}',
            f"TRADE: {'🟢' if signal.direction=='CALL' else '🔴'} {esc(signal.direction)}",'',
            f'{icon} {esc(result.outcome)}','⚠️ Result: Feed-estimated']
        if result.outcome=='UNVERIFIED': lines.append('Reason: '+esc(result.note or 'missing/invalid observation; no price fabricated'))
        if self.settings.TELEGRAM_INCLUDE_AUDIT_DETAILS:
            quote=lambda x:'unavailable' if x is None else format(x,'.10g')
            wins,losses=stats.get('wins'),stats.get('losses')
            rate=100*wins/(wins+losses) if wins is not None and losses is not None and wins+losses else None
            count=lambda x:'—' if x is None else str(x)
            lines += [f'Entry: {quote(result.entry_price)}',f'Expiry: {quote(result.expiry_price)}',
                f'Wins: {count(wins)} | Losses: {count(losses)}',
                f'Win Rate: {rate:.0f}%' if rate is not None else 'Win Rate: N/A',
                f"Draws: {stats.get('draws',0)} | Unverified: {stats.get('unverified',0)}",
                'Not an independently confirmed Quotex settlement.']
        lines += ['',f'╚══════ #{self._tag(signal)} ══════╝']
        return '\n'.join(lines)

    async def send_signal(self,signal,deadline=None):
        return await self.send(self.format_signal(signal),deadline=deadline)
    async def send_result(self,signal,result,stats=None):
        return await self.send(self.format_result(signal,result,stats))
    async def send_text(self,text): return await self.send(text)
