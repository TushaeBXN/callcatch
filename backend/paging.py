"""
Owner notifications and the emergency escalation chain.

notify_owner must never make the caller wait. dispatch() starts the work on a
background thread and returns at once, so the assistant can speak the safety
instruction while the page goes out (docs/call-flow.md, "Emergencies").

Emergency chain (docs/call-flow.md, "If the page fails"):
  1. Voice page the on-call number. The page counts only when the person
     presses 1 to acknowledge. Retry on no acknowledgement.
  2. Then voice page the backup on-call number, with the same retries.
  3. Then text the details to the on-call and backup numbers.
  4. At every failed step, alert the CallCatch operator and log it.

Status returned to the model (prompt section 6):
  - "delivered" only once a page for this call was acknowledged, or a text to
    the on-call or backup number has a delivery receipt.
  - "pending" otherwise. The first call always returns "pending", because the
    chain has only just started. A later notify_owner call for the same call
    (the "updated details" page) returns "delivered" if the chain has succeeded.

Safety properties that MUST stay true:
  - Recipients come only from the client config and operator env vars, never
    from tool arguments.
  - Logs and operator alerts never contain the caller's words. The full
    summary goes only to the business and the per-client page log.

Limit: jobs live in this process. A restart mid-escalation loses the job.
TODO(me): move to a durable queue before running more than one server process.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from backend.adapters.twilio_voice_adapter import page_twiml

log = logging.getLogger("callcatch.paging")

ON_CALL = "on_call"
BACKUP = "backup"


# ---------------------------------------------------------------------------
# Settings and channels
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Timings:
    attempts_per_number: int = 2
    retry_delay_s: float = 15.0
    ack_timeout_s: float = 60.0
    poll_s: float = 3.0

    @classmethod
    def from_env(cls) -> "Timings":
        # TODO(me): retry count and spacing are still open in docs/call-flow.md
        # ("If the page fails"). These defaults are placeholders until decided.
        return cls(
            attempts_per_number=max(1, int(os.environ.get("PAGE_ATTEMPTS_PER_NUMBER", "2"))),
            retry_delay_s=float(os.environ.get("PAGE_RETRY_DELAY_SECONDS", "15")),
            ack_timeout_s=float(os.environ.get("PAGE_ACK_TIMEOUT_SECONDS", "60")),
        )


@dataclass
class Channels:
    """The outside world, injectable for tests. Each send returns delivered/pending/failed."""
    send_sms: Callable[[str, str], str]
    send_email: Callable[[str, str, str], str]
    place_call: Callable[[str, str], "str | None"]
    call_status: Callable[[str], "str | None"]
    sleep: Callable[[float], None] = time.sleep


def default_channels() -> Channels:
    from backend.adapters import email_notify_adapter as em
    from backend.adapters import twilio_notify_adapter as tw

    sms_timeout = float(os.environ.get("SMS_DELIVERY_TIMEOUT_SECONDS", "60"))
    return Channels(
        send_sms=lambda to, body: tw.send_sms(to, body, sms_timeout),
        send_email=em.send_email,
        place_call=tw.place_call,
        call_status=tw.call_status,
    )


def _start_thread(fn: Callable, *args) -> None:
    threading.Thread(target=fn, args=args, daemon=True).start()


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

@dataclass
class PageJob:
    call_sid: str
    client_id: str
    business_name: str
    on_call: str | None
    backup: str | None
    summary: str
    confirmed_role: str | None = None
    confirmed_number: str | None = None
    done: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def confirmed(self) -> bool:
        return self.confirmed_number is not None


_lock = threading.Lock()
_jobs: dict[str, PageJob] = {}
_acks: dict[str, threading.Event] = {}
_base_url: str | None = None

_TERMINAL_CALL_STATUSES = {"completed", "busy", "failed", "no-answer", "canceled"}


def remember_base_url(url: str) -> None:
    """Fallback for the ack webhook's address when PUBLIC_BASE_URL isn't set."""
    global _base_url
    if _base_url is None:
        _base_url = url.rstrip("/")


def _public_base_url() -> str | None:
    env = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    return env or _base_url


def acknowledge(page_id: str) -> bool:
    """Called by the ack webhook. True if the page was still open and is now acknowledged."""
    with _lock:
        event = _acks.get(page_id)
    if event is None:
        return False
    event.set()
    return True


def reset_state() -> None:
    """For tests only."""
    global _base_url
    with _lock:
        _jobs.clear()
        _acks.clear()
    _base_url = None


# ---------------------------------------------------------------------------
# Entry point (called by the notify_owner tool)
# ---------------------------------------------------------------------------

def _as_list(value) -> list[str]:
    if not value:
        return []
    items = value if isinstance(value, list) else [value]
    return [str(v) for v in items if v and v != "PRIVATE"]


def _real(value) -> str | None:
    return str(value) if value and value != "PRIVATE" else None


def dispatch(
    args: dict,
    config: dict,
    call_sid: str,
    *,
    channels: Channels | None = None,
    timings: Timings | None = None,
    run: Callable = _start_thread,
) -> str:
    """Start notifications in the background. Never blocks on delivery."""
    channels = channels or default_channels()
    timings = timings or Timings.from_env()

    priority = args.get("priority", "normal")
    summary = str(args.get("summary") or "(no summary)")[:1000]
    client_id = config.get("client_id", "unknown")
    business_name = config.get("business", {}).get("name", "your business")

    notif = config.get("notifications") or {}
    channel = notif.get("channel", "both")
    sms_to = _as_list(notif.get("sms_to")) if channel in ("sms", "both") else []
    email_to = _as_list(notif.get("email_to")) if channel in ("email", "both") else []

    emerg = config.get("emergencies") or {}
    on_call = _real(emerg.get("on_call_number"))
    backup = _real(emerg.get("backup_on_call_number"))

    if priority != "emergency":
        if not (sms_to or email_to):
            return "failed: no notification contacts configured"
        run(_send_summary, client_id, call_sid, business_name, priority, summary,
            sms_to, email_to, channels, run)
        return "pending"

    if not (on_call or backup or sms_to or email_to):
        return "failed: no notification contacts configured"

    status = "pending"
    with _lock:
        job = _jobs.get(call_sid)
        restart = job is None or (job.done and not job.confirmed)
        if restart:
            job = PageJob(call_sid, client_id, business_name, on_call, backup, summary)
            _jobs[call_sid] = job

    if restart:
        if on_call or backup:
            run(_escalate, job, channels, timings, run)
    else:
        with job.lock:
            job.summary = summary  # a running chain picks up the newer details
            confirmed_number = job.confirmed_number
        if confirmed_number:
            status = "delivered"
            run(_send_update, job, confirmed_number, channels)

    # The owner's written summary goes out alongside the page, every time.
    if sms_to or email_to:
        run(_send_summary, client_id, call_sid, business_name, priority, summary,
            sms_to, email_to, channels, run)
    return status


# ---------------------------------------------------------------------------
# Escalation chain
# ---------------------------------------------------------------------------

def _escalate(job: PageJob, channels: Channels, timings: Timings, run: Callable) -> None:
    try:
        _record(job.client_id, job.call_sid, "escalation_started")
        for role in (ON_CALL, BACKUP):
            number = job.on_call if role == ON_CALL else job.backup
            if not number:
                _operator_alert(job.client_id, job.call_sid,
                                f"no {role} number configured, skipping that step", channels, run)
                continue
            if role == BACKUP and number == job.on_call:
                continue  # same phone; paging it again isn't a backup
            for attempt in range(1, timings.attempts_per_number + 1):
                if attempt > 1:
                    channels.sleep(timings.retry_delay_s)
                if _voice_page(job, role, number, attempt, channels, timings):
                    _confirm(job, role, number, "voice_ack")
                    if role == BACKUP:
                        _operator_alert(job.client_id, job.call_sid,
                                        "on-call never acknowledged; backup acknowledged", channels, run)
                    return
                _operator_alert(job.client_id, job.call_sid,
                                f"voice page to {role} not acknowledged "
                                f"(attempt {attempt}/{timings.attempts_per_number})", channels, run)

        # Step 3: text the details to both numbers.
        with job.lock:
            body = _page_text(job)
        for role, number in _unique_numbers(job):
            status = channels.send_sms(number, body)
            _record(job.client_id, job.call_sid, "sms_page", role=role, status=status)
            if status == "delivered" and not job.confirmed:
                _confirm(job, role, number, "sms_delivered")

        if job.confirmed:
            _operator_alert(job.client_id, job.call_sid,
                            f"no voice page acknowledged; details text delivered to {job.confirmed_role}. "
                            "Nobody has confirmed they're responding.", channels, run)
        else:
            _operator_alert(job.client_id, job.call_sid,
                            "CRITICAL: emergency page failed on every channel. Call the business now.",
                            channels, run)
    except Exception:
        log.exception("escalation crashed client=%s call=%s", job.client_id, job.call_sid)
        _operator_alert(job.client_id, job.call_sid,
                        "CRITICAL: escalation crashed. Call the business now.", channels, run)
    finally:
        with job.lock:
            job.done = True
        _record(job.client_id, job.call_sid, "escalation_finished",
                confirmed_role=job.confirmed_role)


def _voice_page(job: PageJob, role: str, number: str, attempt: int,
                channels: Channels, timings: Timings) -> bool:
    """Place one voice page and wait for the acknowledgement. True only if acknowledged."""
    page_id = uuid.uuid4().hex
    event = threading.Event()
    base = _public_base_url()
    ack_url = f"{base}/page/{page_id}/ack" if base else None

    with job.lock:
        spoken = f"This is an emergency page from CallCatch for {job.business_name}. {job.summary}"
    with _lock:
        _acks[page_id] = event
    try:
        call_sid = channels.place_call(number, page_twiml(spoken, ack_url))
        if call_sid is None:
            _record(job.client_id, job.call_sid, "voice_page", role=role, attempt=attempt, status="not_placed")
            return False
        if ack_url is None:
            log.error("PUBLIC_BASE_URL not set: voice pages can't be acknowledged client=%s", job.client_id)

        deadline = time.monotonic() + timings.ack_timeout_s
        ended = False
        while time.monotonic() < deadline:
            if event.wait(timings.poll_s):
                break
            if ended:
                break  # call ended one poll ago and no ack arrived in the grace period
            ended = channels.call_status(call_sid) in _TERMINAL_CALL_STATUSES

        acked = event.is_set()
        _record(job.client_id, job.call_sid, "voice_page", role=role, attempt=attempt,
                status="acknowledged" if acked else "not_acknowledged")
        return acked
    finally:
        with _lock:
            _acks.pop(page_id, None)


def _confirm(job: PageJob, role: str, number: str, how: str) -> None:
    with job.lock:
        job.confirmed_role = role
        job.confirmed_number = number
    _record(job.client_id, job.call_sid, "confirmed", role=role, how=how)


def _unique_numbers(job: PageJob) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for role, number in ((ON_CALL, job.on_call), (BACKUP, job.backup)):
        if number and number not in (n for _, n in out):
            out.append((role, number))
    return out


def _page_text(job: PageJob) -> str:
    return (
        f"[URGENT] CallCatch emergency for {job.business_name}\n"
        f"Call ID: {job.call_sid}\n"
        f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        f"{job.summary}"
    )


def _send_update(job: PageJob, number: str, channels: Channels) -> None:
    with job.lock:
        body = "UPDATE: " + _page_text(job)
    status = channels.send_sms(number, body)
    _record(job.client_id, job.call_sid, "sms_update", status=status)


# ---------------------------------------------------------------------------
# Owner summary (every call)
# ---------------------------------------------------------------------------

def _send_summary(client_id: str, call_sid: str, business_name: str, priority: str, summary: str,
                  sms_to: list[str], email_to: list[str], channels: Channels, run: Callable) -> None:
    tag = "[URGENT] " if priority == "emergency" else ""
    subject = f"{tag}CallCatch message for {business_name}"
    body = (
        f"New message for {business_name}\n"
        f"Call ID: {call_sid}\n"
        f"Priority: {priority.upper()}\n"
        f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        f"{summary}"
    )
    statuses = []
    for number in sms_to:
        statuses.append(channels.send_sms(number, body))
    for addr in email_to:
        statuses.append(channels.send_email(addr, subject, body))
    _record(client_id, call_sid, "owner_summary", statuses=statuses)

    if "delivered" not in statuses and "pending" not in statuses:
        _operator_alert(client_id, call_sid, "owner summary failed on every channel", channels, run)


# ---------------------------------------------------------------------------
# Operator alerts and the page log
# ---------------------------------------------------------------------------

def _operator_alert(client_id: str, call_sid: str, problem: str,
                    channels: Channels, run: Callable) -> None:
    """Tell the CallCatch operator. Never includes the caller's words."""
    text = f"CallCatch operator alert: client={client_id} call={call_sid}: {problem}"
    log.error(text)
    _record(client_id, call_sid, "operator_alert", problem=problem)

    sms_to = _as_list([s.strip() for s in os.environ.get("OPERATOR_SMS_TO", "").split(",")])
    email_to = _as_list([s.strip() for s in os.environ.get("OPERATOR_EMAIL_TO", "").split(",")])
    if not (sms_to or email_to):
        log.critical("no OPERATOR_SMS_TO or OPERATOR_EMAIL_TO set; operator alert only in logs")
        return

    def send():
        for number in sms_to:
            channels.send_sms(number, text)
        for addr in email_to:
            channels.send_email(addr, "CallCatch operator alert", text)

    run(send)  # its own thread, so a slow receipt never delays the chain


def _record(client_id: str, call_sid: str, event: str, **fields) -> None:
    """Append an event to this call's page log (per-client store, same retention as messages)."""
    from backend.tool_executors import _call_dir  # lazy: tool_executors imports this module

    entry = {"at": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
    try:
        with open(_call_dir(client_id, call_sid) / "page_log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        log.exception("couldn't write page log client=%s call=%s", client_id, call_sid)
