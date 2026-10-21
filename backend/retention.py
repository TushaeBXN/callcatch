"""
Automatic deletion of saved call data (docs/safety-and-compliance.md section 6).

Each call's data lives in <data root>/<client_id>/<call_sid>/ (message.json,
page_log.jsonl). A call folder is deleted once its newest file is older than
that client's data.retention_days. Using the newest file means a call that is
still writing its page log is never deleted underneath itself.

If a client's config is missing or its retention_days is invalid (for example
an offboarded client whose data wasn't removed yet), MAX_RETENTION_DAYS applies:
data is never deleted early by mistake, and never kept past our maximum.
Offboarding still deletes a client's data at once (docs/offboarding.md step 3.3).

Runs hourly inside the server (app.py), or by hand:
  python -m backend.retention            # delete expired call data
  python -m backend.retention --dry-run  # only report what would be deleted

Logs contain client IDs and counts only, never call contents.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from backend.config_schema import MAX_RETENTION_DAYS, load_yaml

log = logging.getLogger("callcatch.retention")

_REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = _REPO_ROOT / "clients"
_DAY_S = 24 * 60 * 60


def data_root() -> Path:
    # Same default as backend/tool_executors.py.
    return Path(os.environ.get("CALLCATCH_DATA_DIR", Path.home() / ".callcatch" / "calls")).expanduser()


@dataclass
class SweepReport:
    deleted: dict[str, int] = field(default_factory=dict)    # client_id -> call folders removed
    kept: dict[str, int] = field(default_factory=dict)       # client_id -> call folders still in date
    fallback_clients: list[str] = field(default_factory=list)  # used MAX_RETENTION_DAYS
    errors: list[str] = field(default_factory=list)

    @property
    def total_deleted(self) -> int:
        return sum(self.deleted.values())


def retention_days_for(client_id: str, clients_dir: Path = CLIENTS_DIR) -> int | None:
    """The client's data.retention_days, or None if it can't be read or is out of range."""
    try:
        cfg = load_yaml(clients_dir / client_id / "config.yaml")
        days = cfg["data"]["retention_days"]
    except Exception:
        return None
    if isinstance(days, int) and not isinstance(days, bool) and 1 <= days <= MAX_RETENTION_DAYS:
        return days
    return None


def _newest_mtime(call_dir: Path) -> float:
    newest = call_dir.lstat().st_mtime
    for p in call_dir.rglob("*"):
        try:
            newest = max(newest, p.lstat().st_mtime)
        except OSError:
            continue
    return newest


def sweep(
    root: Path | None = None,
    clients_dir: Path = CLIENTS_DIR,
    now: float | None = None,
    dry_run: bool = False,
) -> SweepReport:
    """Delete every call folder older than its client's retention period."""
    root = root or data_root()
    now = time.time() if now is None else now
    report = SweepReport()
    if not root.is_dir():
        return report

    for client_dir in sorted(root.iterdir()):
        if client_dir.is_symlink() or not client_dir.is_dir():
            continue  # we only ever create real folders here; don't follow anything else
        client_id = client_dir.name
        days = retention_days_for(client_id, clients_dir)
        if days is None:
            days = MAX_RETENTION_DAYS
            report.fallback_clients.append(client_id)
        cutoff = now - days * _DAY_S

        for call_dir in sorted(client_dir.iterdir()):
            if call_dir.is_symlink() or not call_dir.is_dir():
                continue
            try:
                if _newest_mtime(call_dir) >= cutoff:
                    report.kept[client_id] = report.kept.get(client_id, 0) + 1
                    continue
                if not dry_run:
                    shutil.rmtree(call_dir)
                report.deleted[client_id] = report.deleted.get(client_id, 0) + 1
            except OSError as e:
                report.errors.append(f"{client_id}/{call_dir.name}: {type(e).__name__}")

    _log_report(report, dry_run)
    return report


def _log_report(report: SweepReport, dry_run: bool) -> None:
    verb = "would delete" if dry_run else "deleted"
    for client_id, n in report.deleted.items():
        log.info("retention: %s %d call folder(s) for client=%s", verb, n, client_id)
    for client_id in report.fallback_clients:
        log.warning("retention: no valid data.retention_days for client=%s; used the %d-day maximum",
                    client_id, MAX_RETENTION_DAYS)
    for err in report.errors:
        log.error("retention: couldn't delete %s", err)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delete call data older than each client's retention period.")
    parser.add_argument("--dry-run", action="store_true", help="report only, delete nothing")
    args = parser.parse_args(argv)

    report = sweep(dry_run=args.dry_run)
    verb = "Would delete" if args.dry_run else "Deleted"
    print(f"{verb} {report.total_deleted} call folder(s) under {data_root()}.")
    for client_id, n in sorted(report.deleted.items()):
        print(f"  {client_id}: {n}")
    for client_id in report.fallback_clients:
        print(f"  WARNING {client_id}: no valid data.retention_days, used the {MAX_RETENTION_DAYS}-day maximum")
    for err in report.errors:
        print(f"  ERROR {err}")
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
