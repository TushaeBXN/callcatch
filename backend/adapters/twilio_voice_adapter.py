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


def validate_signature(request_url: str, post_params: dict, signature: str) -> bool:
    """
    Verify that a webhook request actually came from Twilio.

    Set TWILIO_WEBHOOK_SECRET (auth token) in .env.
    Returns True when the signature matches, or when validation is disabled
    (TWILIO_SKIP_VALIDATION=1) for local development.
    """
    if os.environ.get("TWILIO_SKIP_VALIDATION", "").strip() == "1":
        return True
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not auth_token:
        return True
    try:
        from twilio.request_validator import RequestValidator
        return RequestValidator(auth_token).validate(request_url, post_params, signature)
    except Exception:
        return False
