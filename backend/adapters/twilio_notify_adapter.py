"""
Twilio notification channels: SMS and voice pages.

Only this file imports the Twilio SDK for notifications (docs/architecture.md:
nothing outside backend/adapters/ imports a vendor SDK).

Status rule (decision 0001): only "delivered" counts as success. Twilio's
"queued", "accepted", and "sent" mean the carrier took the message, not that
it reached the phone, so they are reported as "pending".
"""

from __future__ import annotations

import os
import time

TERMINAL_CALL_STATUSES = {"completed", "busy", "failed", "no-answer", "canceled"}


def _client():
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not (account_sid and auth_token):
        return None
    from twilio.rest import Client as TwilioClient
    return TwilioClient(account_sid, auth_token)


def send_sms(to: str, body: str, timeout_s: float = 60.0) -> str:
    """
    Send a text and wait for a delivery receipt.

    Returns "delivered", "pending" (accepted or sent, no receipt yet), or "failed".
    Call this from a background worker, never inside a webhook request.
    """
    from_number = os.environ.get("NOTIFY_SMS_FROM", "")
    try:
        client = _client()
        if client is None or not from_number:
            return "failed"
        msg = client.messages.create(to=to, from_=from_number, body=body[:1600])
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            time.sleep(3)
            status = client.messages(msg.sid).fetch().status
            if status == "delivered":
                return "delivered"
            if status in ("failed", "undelivered", "canceled"):
                return "failed"
        return "pending"
    except Exception:
        return "failed"


def place_call(to: str, twiml: str) -> str | None:
    """Start an outbound voice page. Returns the call SID, or None if it couldn't be placed."""
    from_number = os.environ.get("PAGE_CALL_FROM") or os.environ.get("NOTIFY_SMS_FROM", "")
    try:
        client = _client()
        if client is None or not from_number:
            return None
        call = client.calls.create(to=to, from_=from_number, twiml=twiml)
        return call.sid
    except Exception:
        return None


def call_status(call_sid: str) -> str | None:
    """Current Twilio status of an outbound call, or None if it can't be read."""
    try:
        client = _client()
        if client is None:
            return None
        return client.calls(call_sid).fetch().status
    except Exception:
        return None
