"""
CallCatch webhook server.

Twilio calls these endpoints:
  POST /call/{client_id}/incoming  — a call has arrived
  POST /call/{client_id}/turn      — the caller just said something
  POST /call/{client_id}/status    — call lifecycle event (completed, failed, etc.)

Start with:
  uvicorn app:app --host 0.0.0.0 --port 8000

In production, put this behind an HTTPS reverse proxy (nginx, Caddy, etc.).
Twilio requires HTTPS for production webhooks.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import PlainTextResponse

from backend import paging, retention
from backend.adapters.twilio_voice_adapter import (
    error_twiml,
    greeting_twiml,
    hangup_twiml,
    page_ack_twiml,
    turn_twiml,
    validate_signature,
)
from backend.config_schema import load_client_config
from backend.prompt_builder import build_system_prompt, load_dotenv
from backend.session import CallSession

load_dotenv()

_RETENTION_SWEEP_MINUTES = float(os.environ.get("RETENTION_SWEEP_MINUTES", "60"))


async def _retention_loop():
    """Delete expired call data on startup, then every RETENTION_SWEEP_MINUTES."""
    while True:
        try:
            await asyncio.to_thread(retention.sweep)
        except Exception:
            logging.getLogger("callcatch.retention").exception("retention sweep failed")
        await asyncio.sleep(_RETENTION_SWEEP_MINUTES * 60)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    task = asyncio.create_task(_retention_loop())
    yield
    task.cancel()


app = FastAPI(title="CallCatch", docs_url=None, redoc_url=None, lifespan=_lifespan)

_REPO_ROOT = Path(__file__).resolve().parent
_CLIENTS_DIR = _REPO_ROOT / "clients"

_sessions: dict[str, CallSession] = {}


def _make_adapter():
    provider = os.environ.get("LLM_PROVIDER", "stub").lower()
    if provider == "anthropic":
        from backend.adapters.anthropic_adapter import AnthropicAdapter
        return AnthropicAdapter()
    from backend.adapters.stub_adapter import StubAdapter
    return StubAdapter()


def _action_url(request: Request, client_id: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/call/{client_id}/turn"


def _xml(content: str) -> Response:
    return Response(content=content, media_type="application/xml")


def _verify(request: Request, form: dict) -> bool:
    sig = request.headers.get("X-Twilio-Signature", "")
    return validate_signature(str(request.url), form, sig)


# ---------------------------------------------------------------------------
# Incoming call
# ---------------------------------------------------------------------------

@app.post("/call/{client_id}/incoming")
async def incoming_call(
    client_id: str,
    request: Request,
    CallSid: str = Form(...),
    From: str = Form(default="unknown"),
):
    form = dict(await request.form())
    if not _verify(request, form):
        return PlainTextResponse("Forbidden", status_code=403)

    paging.remember_base_url(str(request.base_url))

    config_path = _CLIENTS_DIR / client_id / "config.yaml"
    if not config_path.exists():
        return _xml(error_twiml())

    try:
        config, result = load_client_config(config_path, require_private=True)
        if not result.ok:
            return _xml(error_twiml())
        system_prompt = build_system_prompt(config_path, require_private=True)
    except Exception:
        return _xml(error_twiml())

    session = CallSession(
        call_sid=CallSid,
        client_id=client_id,
        config=config,
        system_prompt=system_prompt,
        adapter=_make_adapter(),
    )
    _sessions[CallSid] = session

    greeting = config.get("greeting", {}).get("text", "Hello, how can I help you?")
    action_url = _action_url(request, client_id)
    return _xml(greeting_twiml(greeting, action_url))


# ---------------------------------------------------------------------------
# Conversation turn
# ---------------------------------------------------------------------------

@app.post("/call/{client_id}/turn")
async def call_turn(
    client_id: str,
    request: Request,
    CallSid: str = Form(...),
    SpeechResult: str = Form(default=""),
    Confidence: str = Form(default=""),
):
    form = dict(await request.form())
    if not _verify(request, form):
        return PlainTextResponse("Forbidden", status_code=403)

    session = _sessions.get(CallSid)
    if session is None:
        return _xml(
            hangup_twiml(
                "I'm sorry, I lost track of our conversation. Please call back."
            )
        )

    try:
        # Off the event loop, so one caller's LLM turn never stalls other
        # callers or a page acknowledgement.
        reply_text, should_hangup = await asyncio.to_thread(session.process_turn, SpeechResult)
    except Exception:
        return _xml(error_twiml())

    if should_hangup or not reply_text:
        _sessions.pop(CallSid, None)
        farewell = reply_text or "Thank you for calling. Goodbye."
        return _xml(hangup_twiml(farewell))

    action_url = _action_url(request, client_id)
    return _xml(turn_twiml(reply_text, action_url))


# ---------------------------------------------------------------------------
# Status callback (call lifecycle events from Twilio)
# ---------------------------------------------------------------------------

@app.post("/call/{client_id}/status")
async def call_status(
    client_id: str,
    request: Request,
    CallSid: str = Form(...),
    CallStatus: str = Form(default=""),
):
    terminal = {"completed", "failed", "busy", "no-answer", "canceled"}
    if CallStatus in terminal:
        _sessions.pop(CallSid, None)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Emergency page acknowledgement (the on-call person pressed a key)
# ---------------------------------------------------------------------------

@app.post("/page/{page_id}/ack")
async def page_ack(
    page_id: str,
    request: Request,
    Digits: str = Form(default=""),
):
    form = dict(await request.form())
    if not _verify(request, form):
        return PlainTextResponse("Forbidden", status_code=403)

    if Digits.strip() == "1":
        return _xml(page_ack_twiml(paging.acknowledge(page_id)))
    return _xml(page_ack_twiml(False, retry_url=str(request.url)))


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health(request: Request):
    """
    Public: liveness only, for uptime monitors. With HEALTH_TOKEN set and sent
    as "Authorization: Bearer <token>", it also reports the active call count.
    """
    token = os.environ.get("HEALTH_TOKEN", "")
    auth = request.headers.get("Authorization", "")
    if token and hmac.compare_digest(auth.encode(), f"Bearer {token}".encode()):
        return {"status": "ok", "active_calls": len(_sessions)}
    return {"status": "ok"}
