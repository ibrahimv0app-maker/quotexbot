"""Clock-driven entry scheduler.

Timing model (Asia/Karachi display, UTC internally):

    entry slot          12:13:00
    signal send target  12:12:48   (entry - SIGNAL_LEAD_SECONDS)
    permitted window    12:12:45 .. 12:12:50
    expiry              12:14:00   (entry + EXPIRY_SECONDS)

If the process misses the permitted window the opportunity is dropped - a late
signal is never sent pretending the original entry is still available.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.config import Settings

MINUTE = 60


@dataclass(frozen=True)
class EntrySlot:
    entry_ts: int          # intended entry (epoch seconds, minute boundary)
    expiry_ts: int         # intended expiry
    send_from: float       # earliest send time
    send_until: float      # latest send time
    slot_id: str

    def contains(self, now: float) -> bool:
        return self.send_from <= now <= self.send_until

    def is_past(self, now: float) -> bool:
        return now > self.send_until

    def seconds_to_entry(self, now: float) -> float:
        return self.entry_ts - now


def next_entry_slot(now: float, settings: Settings) -> EntrySlot:
    """The next minute-boundary entry slot with its permitted notification window."""
    entry_ts = int(now // MINUTE + 1) * MINUTE
    send_from = entry_ts - 15
    send_until = entry_ts - 10
    return EntrySlot(
        entry_ts=entry_ts,
        expiry_ts=entry_ts + settings.EXPIRY_SECONDS,
        send_from=send_from,
        send_until=send_until,
        slot_id=str(entry_ts),
    )


def slot_for_entry(entry_ts: int, settings: Settings) -> EntrySlot:
    return EntrySlot(
        entry_ts=entry_ts,
        expiry_ts=entry_ts + settings.EXPIRY_SECONDS,
        send_from=entry_ts - 15,
        send_until=entry_ts - 10,
        slot_id=str(entry_ts),
    )


def local_time(ts: float, tz_name: str) -> datetime:
    from zoneinfo import ZoneInfo
    return datetime.fromtimestamp(ts, tz=ZoneInfo(tz_name))


def format_local(ts: float, tz_name: str, with_tz: bool = True) -> str:
    dt = local_time(ts, tz_name)
    base = dt.strftime("%H:%M:%S")
    if not with_tz:
        return base
    short = "PKT" if tz_name == "Asia/Karachi" else (dt.strftime("%Z") or tz_name)
    return f"{base} {short}"


def utc_iso(ts: Optional[float] = None) -> str:
    dt = datetime.fromtimestamp(ts if ts is not None else time.time(), tz=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")
