"""
Proof that the emergency paging chain escalates correctly and never blocks.

Every outside service is faked: no network, no Twilio SDK.

Run:   python -m unittest tests/test_paging.py -v
Needs: nothing beyond the standard library and pyyaml.
"""

import logging
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_DATA_DIR = tempfile.mkdtemp(prefix="callcatch-test-")
os.environ["CALLCATCH_DATA_DIR"] = _DATA_DIR  # before tool_executors reads it

from backend import paging  # noqa: E402
from backend.adapters import twilio_notify_adapter  # noqa: E402
from backend.adapters.twilio_voice_adapter import page_twiml, validate_signature  # noqa: E402

ON_CALL = "+15550199"
BACKUP = "+15550198"
OWNER = "+15550197"
OPERATOR = "+15550101"

logging.disable(logging.CRITICAL)  # operator alerts are asserted on, not printed

FAST = paging.Timings(attempts_per_number=2, retry_delay_s=0, ack_timeout_s=0.2, poll_s=0.01)


def run_now(fn, *args):
    """Run 'background' work inline so tests are deterministic."""
    fn(*args)


class FakeChannels:
    def __init__(self, answers=(), sms_status=None, call_fails=False):
        self.answers = set(answers)          # numbers that press 1
        self.sms_status = sms_status or {}   # number -> status; default "pending"
        self.call_fails = call_fails
        self.calls = []
        self.sms = []
        self.emails = []

    def place_call(self, to, twiml):
        if self.call_fails:
            raise RuntimeError("twilio down")
        self.calls.append(to)
        match = re.search(r"/page/([0-9a-f]{32})/ack", twiml)
        if to in self.answers and match:  # no ack URL means nowhere to press 1
            paging.acknowledge(match.group(1))
        return f"CA{len(self.calls)}"

    def call_status(self, sid):
        return "completed"

    def send_sms(self, to, body):
        self.sms.append((to, body))
        return self.sms_status.get(to, "pending")

    def send_email(self, to, subject, body):
        self.emails.append((to, subject))
        return "pending"

    def channels(self):
        return paging.Channels(
            send_sms=self.send_sms, send_email=self.send_email,
            place_call=self.place_call, call_status=self.call_status,
            sleep=lambda s: None,
        )


def config(on_call=ON_CALL, backup=BACKUP):
    return {
        "client_id": "test-client",
        "business": {"name": "Test HVAC"},
        "emergencies": {"on_call_number": on_call, "backup_on_call_number": backup},
        "notifications": {"channel": "both", "sms_to": [OWNER], "email_to": ["owner@example.invalid"]},
    }


EMERGENCY = {"priority": "emergency", "summary": 'Caller said: "I smell gas"'}


class PagingTest(unittest.TestCase):
    def setUp(self):
        paging.reset_state()
        env = mock.patch.dict(os.environ, {
            "PUBLIC_BASE_URL": "https://callcatch.example.invalid",
            "OPERATOR_SMS_TO": OPERATOR,
            "OPERATOR_EMAIL_TO": "",
        })
        env.start()
        self.addCleanup(env.stop)

    def dispatch(self, fake, args=EMERGENCY, cfg=None, call_sid="CA-test", run=run_now):
        return paging.dispatch(args, cfg or config(), call_sid,
                               channels=fake.channels(), timings=FAST, run=run)

    def operator_alerts(self, fake):
        return [body for to, body in fake.sms if to == OPERATOR]

    # --- never blocks the caller ---

    def test_dispatch_returns_before_any_delivery(self):
        fake = FakeChannels()
        queued = []
        status = self.dispatch(fake, run=lambda fn, *a: queued.append(fn))
        self.assertEqual(status, "pending")
        self.assertEqual(fake.calls, [])
        self.assertEqual(fake.sms, [])
        self.assertTrue(queued, "work should be handed to the background")

    def test_normal_priority_is_pending_and_skips_paging(self):
        fake = FakeChannels(answers={ON_CALL})
        status = self.dispatch(fake, args={"priority": "normal", "summary": "routine"})
        self.assertEqual(status, "pending")
        self.assertEqual(fake.calls, [])
        self.assertIn(OWNER, [to for to, _ in fake.sms])

    # --- the chain ---

    def test_on_call_acknowledges_first_page(self):
        fake = FakeChannels(answers={ON_CALL})
        self.assertEqual(self.dispatch(fake), "pending")
        self.assertEqual(fake.calls, [ON_CALL])
        self.assertEqual(self.operator_alerts(fake), [])

        # The "updated details" call now reports success and texts the update.
        self.assertEqual(self.dispatch(fake), "delivered")
        self.assertTrue(any(to == ON_CALL and body.startswith("UPDATE:") for to, body in fake.sms))

    def test_retries_on_call_then_pages_backup(self):
        fake = FakeChannels(answers={BACKUP})
        self.dispatch(fake)
        self.assertEqual(fake.calls, [ON_CALL, ON_CALL, BACKUP])
        alerts = self.operator_alerts(fake)
        self.assertEqual(sum("on_call not acknowledged" in a for a in alerts), 2)
        self.assertTrue(any("backup acknowledged" in a for a in alerts))
        self.assertEqual(self.dispatch(fake), "delivered")

    def test_sent_but_unconfirmed_text_is_not_success(self):
        fake = FakeChannels(sms_status={ON_CALL: "pending", BACKUP: "pending"})
        self.dispatch(fake)
        self.assertEqual(fake.calls, [ON_CALL, ON_CALL, BACKUP, BACKUP])
        self.assertTrue(any("CRITICAL" in a for a in self.operator_alerts(fake)))
        # A failed chain restarts on the next notify_owner call rather than claiming success.
        fake.calls.clear()
        self.assertEqual(self.dispatch(fake), "pending")
        self.assertEqual(fake.calls[0], ON_CALL)

    def test_delivered_text_confirms_after_voice_fails(self):
        fake = FakeChannels(sms_status={ON_CALL: "delivered"})
        self.dispatch(fake)
        alerts = self.operator_alerts(fake)
        self.assertTrue(any("details text delivered to on_call" in a for a in alerts))
        self.assertFalse(any("CRITICAL" in a for a in alerts))
        self.assertEqual(self.dispatch(fake), "delivered")

    def test_missing_backup_is_reported_not_silent(self):
        fake = FakeChannels(answers=set())
        self.dispatch(fake, cfg=config(backup=None))
        self.assertEqual(fake.calls, [ON_CALL, ON_CALL])
        self.assertTrue(any("no backup number" in a for a in self.operator_alerts(fake)))

    def test_crash_alerts_operator(self):
        fake = FakeChannels(call_fails=True)
        self.dispatch(fake)
        self.assertTrue(any("escalation crashed" in a for a in self.operator_alerts(fake)))

    def test_without_base_url_page_cannot_be_confirmed(self):
        with mock.patch.dict(os.environ, {"PUBLIC_BASE_URL": ""}):
            fake = FakeChannels(answers={ON_CALL})  # they answer, but can't acknowledge
            self.dispatch(fake)
            self.assertIn(BACKUP, fake.calls)
            self.assertNotEqual(self.dispatch(fake), "delivered")

    # --- safety properties ---

    def test_recipients_come_only_from_config(self):
        fake = FakeChannels(answers={ON_CALL})
        self.dispatch(fake, args={**EMERGENCY, "to": "+15550111"})
        sent_to = set(fake.calls) | {to for to, _ in fake.sms}
        self.assertNotIn("+15550111", sent_to)

    def test_operator_alerts_never_include_caller_words(self):
        fake = FakeChannels()
        self.dispatch(fake)
        for alert in self.operator_alerts(fake):
            self.assertNotIn("smell gas", alert)

    def test_no_contacts_fails(self):
        fake = FakeChannels()
        cfg = config(on_call=None, backup=None)
        cfg["notifications"] = {"channel": "both", "sms_to": [], "email_to": []}
        self.assertTrue(self.dispatch(fake, cfg=cfg).startswith("failed"))


class TwilioAdapterTest(unittest.TestCase):
    def fake_client(self, status):
        msg = SimpleNamespace(sid="SM1", status=status)
        messages = mock.Mock(side_effect=lambda sid: SimpleNamespace(fetch=lambda: msg))
        messages.create = mock.Mock(return_value=msg)
        return SimpleNamespace(messages=messages)

    def send(self, status):
        with mock.patch.object(twilio_notify_adapter, "_client", return_value=self.fake_client(status)), \
             mock.patch.object(twilio_notify_adapter.time, "sleep"), \
             mock.patch.dict(os.environ, {"NOTIFY_SMS_FROM": "+15550100"}):
            return twilio_notify_adapter.send_sms(ON_CALL, "hi", timeout_s=0.05)

    def test_sent_is_not_delivered(self):
        self.assertEqual(self.send("sent"), "pending")

    def test_delivered_is_delivered(self):
        self.assertEqual(self.send("delivered"), "delivered")

    def test_undelivered_is_failed(self):
        self.assertEqual(self.send("undelivered"), "failed")


class TwimlAndSignatureTest(unittest.TestCase):
    def test_page_asks_for_keypress_only_with_ack_url(self):
        self.assertIn('action="https://x.invalid/page/abc/ack"', page_twiml("msg", "https://x.invalid/page/abc/ack"))
        self.assertNotIn("<Gather", page_twiml("msg", None))

    def test_signature_fails_closed_without_token(self):
        with mock.patch.dict(os.environ, {"TWILIO_SKIP_VALIDATION": "", "TWILIO_AUTH_TOKEN": ""}):
            self.assertFalse(validate_signature("https://x.invalid/page/abc/ack", {"Digits": "1"}, ""))


if __name__ == "__main__":
    unittest.main()
