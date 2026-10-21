"""
Email notification channel (SMTP).

SMTP can only tell us the server accepted the message, never that it reached
an inbox, so this channel never reports "delivered". It is the second channel
behind SMS (decision 0001), not a confirmation path.
"""

from __future__ import annotations

import os
import smtplib
import socket
from email.message import EmailMessage


def send_email(to: str, subject: str, body: str) -> str:
    """Returns "pending" (accepted by the SMTP server) or "failed"."""
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    from_addr = os.environ.get("NOTIFY_EMAIL_FROM", smtp_user)
    if not (smtp_host and smtp_user and smtp_pass):
        return "failed"
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to
        msg.set_content(body)
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as s:
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.send_message(msg)
        return "pending"
    except (smtplib.SMTPException, socket.error, OSError):
        return "failed"
