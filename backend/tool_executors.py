"""
Real implementations of the three assistant tools.

Each executor receives (arguments: dict, config: dict, call_sid: str) and returns
a plain string that goes back to the model as the tool result.

Safety properties that MUST stay true:
  - save_message writes only to this client's data directory.
  - notify_owner reads recipients ONLY from config, never from arguments.
  - check_or_book_slot only touches this client's calendar.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend import paging

log = logging.getLogger("callcatch.tools")

_DATA_ROOT = Path(os.environ.get("CALLCATCH_DATA_DIR", Path.home() / ".callcatch" / "calls")).expanduser()


def _call_dir(client_id: str, call_sid: str) -> Path:
    d = _DATA_ROOT / client_id / call_sid
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# save_message
# ---------------------------------------------------------------------------

def execute_save_message(args: dict, config: dict, call_sid: str) -> str:
    """Write a JSON record for this call to disk."""
    client_id = config.get("client_id", "unknown")
    record = {
        "call_sid": call_sid,
        "client_id": client_id,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        **args,
    }
    dest = _call_dir(client_id, call_sid) / "message.json"
    dest.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    return "saved"


# ---------------------------------------------------------------------------
# notify_owner
# ---------------------------------------------------------------------------

def execute_notify_owner(args: dict, config: dict, call_sid: str) -> str:
    """
    Start the owner summary and, for emergencies, the paging chain.

    Returns immediately so the caller never hears dead air; delivery happens in
    the background (backend/paging.py). Recipients come ONLY from config.

    Returns "delivered" (confirmed for this call), "pending", or "failed".
    """
    return paging.dispatch(args, config, call_sid)


# ---------------------------------------------------------------------------
# check_or_book_slot
# ---------------------------------------------------------------------------

def execute_check_or_book_slot(args: dict, config: dict, call_sid: str) -> str:
    """
    Calendar check/book. Returns real results if Google Calendar is configured;
    otherwise returns a polite "not available" string the model can relay.
    """
    booking_cfg = config.get("booking", {})
    if not booking_cfg.get("enabled", False):
        return "Booking is not set up for this business yet."

    credentials_file = booking_cfg.get("google_credentials_file", "")
    calendar_id = booking_cfg.get("calendar_id", "")
    if not (credentials_file and calendar_id):
        return "Booking is not set up for this business yet."

    try:
        return _gcal_check_or_book(
            action=args.get("action", "check"),
            requested_time=args.get("requested_time", ""),
            slot_id=args.get("slot_id"),
            calendar_id=calendar_id,
            credentials_file=credentials_file,
            config=config,
        )
    except Exception:
        # Details stay in our logs; the model could read them out to the caller.
        log.exception("booking failed client=%s call=%s", config.get("client_id"), call_sid)
        return "Booking isn't available right now."


def _gcal_check_or_book(
    action: str,
    requested_time: str,
    slot_id: str | None,
    calendar_id: str,
    credentials_file: str,
    config: dict,
) -> str:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    scopes = ["https://www.googleapis.com/auth/calendar"]
    creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    slot_duration = config.get("booking", {}).get("slot_minutes", 30)

    if action == "check":
        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = now.replace(hour=23, minute=59).isoformat()
        events_result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=10,
            )
            .execute()
        )
        events = events_result.get("items", [])
        busy = {
            e["start"].get("dateTime", e["start"].get("date"))
            for e in events
        }
        lines = [f"Available slots (each {slot_duration} min):"]
        for hour in range(8, 18):
            for minute in (0, 30):
                slot_start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                slot_str = slot_start.isoformat()
                if slot_str not in busy:
                    sid = f"{hour:02d}{minute:02d}"
                    lines.append(f"  slot_id={sid}  {slot_start.strftime('%I:%M %p')}")
        return "\n".join(lines) if len(lines) > 1 else "No available slots today."

    if action == "book":
        if not slot_id:
            return "Please provide a slot_id from a previous check."
        hour = int(slot_id[:2])
        minute = int(slot_id[2:])
        now = datetime.now(timezone.utc)
        start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        end = start.replace(minute=minute + slot_duration if minute + slot_duration < 60 else 0,
                            hour=hour + (1 if minute + slot_duration >= 60 else 0))
        business_name = config.get("business", {}).get("name", "CallCatch")
        event = {
            "summary": f"Callback — {business_name}",
            "description": f"Booked via CallCatch for caller.",
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
        }
        created = service.events().insert(calendarId=calendar_id, body=event).execute()
        return f"Booked: {start.strftime('%I:%M %p')} — confirmation ID {created.get('id', 'n/a')}"

    return f"Unknown action: {action}"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

EXECUTORS = {
    "save_message":       execute_save_message,
    "notify_owner":       execute_notify_owner,
    "check_or_book_slot": execute_check_or_book_slot,
}


def run_tool(name: str, arguments: dict, config: dict, call_sid: str) -> str:
    fn = EXECUTORS.get(name)
    if fn is None:
        return f"Unknown tool: {name}"
    try:
        return fn(arguments, config, call_sid)
    except Exception:
        log.exception("tool %s failed client=%s call=%s", name, config.get("client_id"), call_sid)
        return "Tool error: the system couldn't complete this step."
