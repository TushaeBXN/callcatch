"""
Proof that the webhook server doesn't expose more than it should.

Run:   python -m unittest tests/test_app.py -v
Needs: fastapi, httpx, python-multipart. No network.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import app  # noqa: E402

TOKEN = "test-health-token"


class HealthTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app.app)
        env = mock.patch.dict(os.environ, {"HEALTH_TOKEN": TOKEN})
        env.start()
        self.addCleanup(env.stop)

    def get(self, auth=None):
        headers = {"Authorization": auth} if auth else {}
        r = self.client.get("/health", headers=headers)
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_public_shows_status_only(self):
        self.assertEqual(self.get(), {"status": "ok"})

    def test_wrong_token_shows_status_only(self):
        self.assertEqual(self.get("Bearer wrong"), {"status": "ok"})
        self.assertEqual(self.get(TOKEN), {"status": "ok"})  # missing "Bearer "

    def test_right_token_shows_call_count(self):
        self.assertIn("active_calls", self.get(f"Bearer {TOKEN}"))

    def test_unset_token_never_shows_call_count(self):
        with mock.patch.dict(os.environ, {"HEALTH_TOKEN": ""}):
            self.assertEqual(self.get("Bearer "), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
