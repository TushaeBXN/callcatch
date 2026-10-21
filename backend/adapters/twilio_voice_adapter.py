"""
Twilio voice I/O layer.

Generates TwiML responses and validates incoming Twilio webhook signatures.
This is not an LLMAdapter — it handles the speech/TTS side of the call,
not the language model side.

How Twilio voice works:
  1. A call arrives. Twilio POST-s to /call/{client_id}/incoming.
  2. We reply with TwiML that says something and then listens (Gather).
  3. Twilio speech-to-texts what the caller says, then POST-s the result
     back to our action URL (the /turn endpoint).
  4. We reply with more TwiML. Repeat until <Hangup>.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from xml.dom.minidom import parseString


_POLLY_VOICE = os.environ.get("TWILIO_TTS_VOICE", "Polly.Joanna")
_GATHER_TIMEOUT = int(os.environ.get("GATHER_TIMEOUT_SECONDS", "5"))
_SPEECH_TIMEOUT = os.environ.get("GATHER_SPEECH_TIMEOUT", "auto")


def _twiml(root_elem: ET.Element) -> str:
    raw = ET.tostring(root_elem, encoding="unicode", xml_declaration=False)
    pretty = parseString(f"<?xml version='1.0'?>\n{raw}").toprettyxml(indent="  ")
    lines = [l for l in pretty.splitlines() if l.strip() and not l.startswith("<?xml")]
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + "\n".join(lines)


def _say(parent: ET.Element, text: str) -> ET.Element:
    say = ET.SubElement(parent, "Say", voice=_POLLY_VOICE)
    say.text = text
    return say


def greeting_twiml(greeting_text: str, action_url: str) -> str:
    """
    TwiML for the opening of a call: play the greeting and start listening.
    """
    response = ET.Element("Response")
    gather = ET.SubElement(
        response, "Gather",
        input="speech",
        action=action_url,
        method="POST",
        timeout=str(_GATHER_TIMEOUT),
        speechTimeout=_SPEECH_TIMEOUT,
    )
    _say(gather, greeting_text)
    # If the caller is silent, redirect to the same turn endpoint with empty speech
    redirect = ET.SubElement(response, "Redirect", method="POST")
    redirect.text = action_url
    return _twiml(response)


def turn_twiml(text_to_speak: str, action_url: str) -> str:
    """
    TwiML for mid-call: speak the assistant's reply, then listen for the next turn.
    """
    response = ET.Element("Response")
    gather = ET.SubElement(
        response, "Gather",
        input="speech",
        action=action_url,
        method="POST",
        timeout=str(_GATHER_TIMEOUT),
        speechTimeout=_SPEECH_TIMEOUT,
    )
    _say(gather, text_to_speak)
    redirect = ET.SubElement(response, "Redirect", method="POST")
    redirect.text = action_url
    return _twiml(response)


def hangup_twiml(farewell_text: str) -> str:
    """
    TwiML for ending the call: speak the goodbye, then hang up.
    """
    response = ET.Element("Response")
    _say(response, farewell_text)
    ET.SubElement(response, "Hangup")
    return _twiml(response)


def error_twiml() -> str:
    """Fallback TwiML when something goes wrong internally."""
    response = ET.Element("Response")
    _say(
        response,
        "I'm sorry, something went wrong on our end. Please try calling back. "
        "If this is an emergency, hang up and call 9-1-1.",
    )
    ET.SubElement(response, "Hangup")
    return _twiml(response)


def page_twiml(message: str, ack_url: str | None) -> str:
    """
    TwiML for an outbound emergency page to the on-call person.

    The page counts only when they press 1, which posts to ack_url. A voicemail
    or an unanswered call never presses 1, so it never counts. With no ack_url
    the message is still read out, but the page can't be confirmed.
    """
    response = ET.Element("Response")
    parent = response
    if ack_url:
        parent = ET.SubElement(
            response, "Gather",
            input="dtmf", numDigits="1", action=ack_url, method="POST", timeout="10",
        )
    for _ in range(2):
        _say(parent, message[:600])
        if ack_url:
            _say(parent, "Press 1 to acknowledge this page.")
    _say(response, "No acknowledgement received. Goodbye.")
    return _twiml(response)


def page_ack_twiml(acknowledged: bool, retry_url: str | None = None) -> str:
    """Reply to a key press on an emergency page."""
    response = ET.Element("Response")
    if acknowledged:
        _say(response, "Acknowledged. Thank you. The details are also in your messages.")
    elif retry_url:
        gather = ET.SubElement(
            response, "Gather",
            input="dtmf", numDigits="1", action=retry_url, method="POST", timeout="10",
        )
        _say(gather, "Press 1 to acknowledge this page.")
    else:
        _say(response, "This page has expired. The team is being contacted another way.")
    ET.SubElement(response, "Hangup")
    return _twiml(response)


def validate_signature(request_url: str, post_params: dict, signature: str) -> bool:
    """
    Verify that a webhook request actually came from Twilio.

    Uses TWILIO_AUTH_TOKEN from .env. Fails closed: with no token, every
    request is rejected, because a forged page acknowledgement would stop an
    emergency escalation. Only TWILIO_SKIP_VALIDATION=1 (local development)
    turns the check off.
    """
    if os.environ.get("TWILIO_SKIP_VALIDATION", "").strip() == "1":
        return True
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not auth_token:
        return False
    try:
        from twilio.request_validator import RequestValidator
        return RequestValidator(auth_token).validate(request_url, post_params, signature)
    except Exception:
        return False
