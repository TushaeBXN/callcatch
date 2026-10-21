"""
Proof that saved call data is deleted on time, and nothing else is.

Run:   python -m unittest tests/test_retention.py -v
Needs: pyyaml. No network.
"""

import logging
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Always a throwaway folder: one test below deletes everything under it.
os.environ["CALLCATCH_DATA_DIR"] = tempfile.mkdtemp(prefix="callcatch-test-")

from backend import retention, tool_executors  # noqa: E402
from backend.config_schema import MAX_RETENTION_DAYS  # noqa: E402

logging.disable(logging.CRITICAL)

DAY = 24 * 60 * 60
NOW = 1_800_000_000.0


class RetentionTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        self.clients = base / "clients"
        self.data = base / "calls"
        self.outside = base / "outside"
        self.outside.mkdir()

    def client(self, client_id, retention_days):
        d = self.clients / client_id
        d.mkdir(parents=True)
        (d / "config.yaml").write_text(f"data:\n  retention_days: {retention_days}\n")

    def call(self, client_id, call_sid, age_days, files=("message.json",)):
        d = self.data / client_id / call_sid
        d.mkdir(parents=True)
        for name in files:
            p = d / name
            p.write_text("{}")
            os.utime(p, (NOW - age_days * DAY,) * 2)
        os.utime(d, (NOW - age_days * DAY,) * 2)
        return d

    def sweep(self, **kw):
        return retention.sweep(root=self.data, clients_dir=self.clients, now=NOW, **kw)

    def test_deletes_only_calls_past_retention(self):
        self.client("acme", 30)
        old = self.call("acme", "CA_old", 31)
        new = self.call("acme", "CA_new", 29)
        report = self.sweep()
        self.assertFalse(old.exists())
        self.assertTrue(new.exists())
        self.assertEqual(report.deleted, {"acme": 1})
        self.assertEqual(report.kept, {"acme": 1})

    def test_each_client_uses_its_own_period(self):
        self.client("short", 7)
        self.client("long", 90)
        short_call = self.call("short", "CA1", 10)
        long_call = self.call("long", "CA2", 10)
        self.sweep()
        self.assertFalse(short_call.exists())
        self.assertTrue(long_call.exists())

    def test_call_still_writing_its_page_log_is_kept(self):
        self.client("acme", 30)
        d = self.call("acme", "CA_live", 31)
        log = d / "page_log.jsonl"
        log.write_text("{}\n")
        os.utime(log, (NOW - 60,) * 2)
        self.sweep()
        self.assertTrue(d.exists())

    def test_missing_config_falls_back_to_maximum(self):
        within = self.call("gone", "CA1", MAX_RETENTION_DAYS - 1)
        past = self.call("gone", "CA2", MAX_RETENTION_DAYS + 1)
        report = self.sweep()
        self.assertTrue(within.exists(), "never delete early because a config is missing")
        self.assertFalse(past.exists(), "never keep past the maximum")
        self.assertEqual(report.fallback_clients, ["gone"])

    def test_invalid_retention_falls_back_to_maximum(self):
        for bad, client_id in (("0", "zero"), ('"30"', "string"), (str(MAX_RETENTION_DAYS + 1), "too_long")):
            self.client(client_id, bad)
            self.call(client_id, "CA1", 31)
        report = self.sweep()
        self.assertEqual(sorted(report.fallback_clients), ["string", "too_long", "zero"])
        self.assertEqual(report.total_deleted, 0)

    def test_dry_run_deletes_nothing(self):
        self.client("acme", 30)
        old = self.call("acme", "CA_old", 31)
        report = self.sweep(dry_run=True)
        self.assertTrue(old.exists())
        self.assertEqual(report.deleted, {"acme": 1})

    def test_symlinks_are_never_followed(self):
        self.client("acme", 1)
        target = self.outside / "precious"
        target.mkdir()
        (target / "keep.txt").write_text("not call data")
        os.utime(target / "keep.txt", (NOW - 100 * DAY,) * 2)
        (self.data / "acme").mkdir(parents=True)
        (self.data / "acme" / "CA_link").symlink_to(target)
        (self.data / "linked_client").symlink_to(self.outside)
        self.sweep()
        self.assertTrue((target / "keep.txt").exists())

    def test_no_data_folder_is_fine(self):
        self.assertEqual(self.sweep().total_deleted, 0)

    def test_save_message_output_is_swept(self):
        """What save_message writes is exactly what the sweep removes."""
        # Guard: if another module imported tool_executors first with a real
        # data folder, refuse rather than delete it.
        if "callcatch-test-" not in str(tool_executors._DATA_ROOT):
            self.skipTest(f"data root isn't a test folder: {tool_executors._DATA_ROOT}")
        cfg = {"client_id": "acme-int"}
        tool_executors.execute_save_message({"problem": "x", "urgency": "routine"}, cfg, "CA_int")
        call_dir = tool_executors._DATA_ROOT / "acme-int" / "CA_int"
        self.assertTrue((call_dir / "message.json").exists())
        retention.sweep(root=tool_executors._DATA_ROOT, clients_dir=self.clients,
                        now=time.time() + (MAX_RETENTION_DAYS + 1) * DAY)
        self.assertFalse(call_dir.exists())


class DataRootTest(unittest.TestCase):
    def test_tilde_is_expanded(self):
        with mock.patch.dict(os.environ, {"CALLCATCH_DATA_DIR": "~/.callcatch/calls"}):
            self.assertEqual(retention.data_root(), Path.home() / ".callcatch" / "calls")


if __name__ == "__main__":
    unittest.main()
