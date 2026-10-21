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
import os
import smtplib
import socket
import time
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

_DATA_ROOT = Path(os.environ.get("CALLCATCH_DATA_DIR", Path.home() / ".callcatch" / "calls"))


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
    Send a summary to the owner via SMS (Twilio) and email (SMTP).

    Recipients come ONLY from config["notifications"]. The model cannot
    supply or override them.

    Returns "delivered", "pending", or "failed".
    """
    priority: str = args.get("priority", "normal")
    summary: str = args.get("summary", "(no summary)")
    client_id = config.get("client_id", "unknown")
    notif = config.get("notifications", {})

    sms_to: str | None = notif.get("sms_to")
    email_to: str | None = notif.get("email_to")
    business_name: str = config.get("business", {}).get("name", "your business")

    if not sms_to and not email_to:
        return "failed: no notification contacts configured"

    tag = "[URGENT] " if priority == "emergency" else ""
    subject = f"{tag}CallCatch message for {business_name}"
    body = (
        f"New message for {business_name}\n"
        f"Call ID: {call_sid}\n"
        f"Priority: {priority.upper()}\n"
        f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        f"{summary}"
    )

    delivered_count = 0
    failed_count = 0

    if sms_to:
        result = _send_sms(sms_to, body[:1600])
        if result:
            delivered_count += 1
        else:
            failed_count += 1

    if email_to:
        result = _send_email(email_to, subject, body)
        if result:
            delivered_count += 1
        else:
            failed_count += 1

    total = (1 if sms_to else 0) + (1 if email_to else 0)
    if delivered_count == total:
        return "delivered"
    if delivered_count > 0:
        return "pending"
    return "failed"


def _send_sms(to: str, body: str) -> bool:
    try:
        from twilio.rest import Client as TwilioClient
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        from_number = os.environ.get("NOTIFY_SMS_FROM", "")
        if not (account_sid and auth_token and from_number):
            return False
        client = TwilioClient(account_sid, auth_token)
        msg = client.messages.create(to=to, from_=from_number, body=body)
        for _ in range(6):
            time.sleep(2)
            fetched = client.messages(msg.sid).fetch()
            if fetched.status in ("delivered", "sent"):
                return True
            if fetched.status in ("failed", "undelivered"):
                return False
        return False
    except Exception:
        return False


def _send_email(to: str, subject: str, body: str) -> bool:
    try:
        smtp_host = os.environ.get("SMTP_HOST", "")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_pass = os.environ.get("SMTP_PASS", "")
        from_addr = os.environ.get("NOTIFY_EMAIL_FROM", smtp_user)
        if not (smtp_host and smtp_user and smtp_pass):
            return False
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to
        msg.set_content(body)
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as s:
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.send_message(msg)
        return True
    except (smtplib.SMTPException, socket.error, OSError):
        return False


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
    except Exception as e:
        return f"Booking check failed: {e}"


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
    except Exception as e:
        return f"Tool error: {e}"
