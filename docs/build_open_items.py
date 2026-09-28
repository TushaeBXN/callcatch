"""
Builds docs/open-items.md: every TODO(me) and VERIFY in the repo, grouped by
phase and file, plus a scan for anything that looks like real data.

    python docs/build_open_items.py          # rewrite docs/open-items.md
    python docs/build_open_items.py --scan   # print only the real-data scan

Standard library only. It scans files git tracks, plus new files that aren't
gitignored, so .env and private/ folders are never read.
"""

import re
import subprocess
import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "open-items.md"

# Generated copies are skipped (their sources are scanned instead).
GENERATED = {"docs/open-items.md", "tests/scenarios.md", "docs/unit-economics.md"}
SELF = {"docs/build_open_items.py"}

PHASES = OrderedDict([
    ("Phase 1: Repo and guardrails", ["README.md", "SECURITY.md", "CONTRIBUTING.md", ".env.example", ".gitignore",
                                      ".pre-commit-config.yaml", ".github/", "docs/reactivation-later.md", "requirements.txt"]),
    ("Phase 2: Call flow", ["docs/call-flow.md"]),
    ("Phase 3: Prompt and safety", ["prompts/", "docs/safety-and-compliance.md"]),
    ("Phase 4: Tests and adapters", ["tests/", "backend/adapters/", "backend/tools.py", "backend/prompt_builder.py", "backend/README.md"]),
    ("Phase 5: Client config", ["clients/", "backend/config_schema.py"]),
    ("Phase 6: Onboarding and offboarding", ["docs/onboarding.md", "docs/offboarding.md"]),
    ("Phase 7: Service agreement", ["docs/service-agreement-outline.md"]),
    ("Phase 8: Unit economics", ["docs/unit_economics.py", "docs/templates/", "docs/build_unit_economics_doc.py"]),
    ("Phase 9: Architecture, monitoring, roadmap", ["docs/architecture.md", "docs/monitoring.md", "docs/roadmap.md", "infra/"]),
])

MARKER = re.compile(r"TODO\(me\)|VERIFY")
FILL_INS = re.compile(r"\[(EMAIL|REPO NAME|COMPANY NAME)\]")


def repo_files():
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return sorted({p for p in out.splitlines() if (ROOT / p).is_file()})


def phase_of(path):
    for phase, prefixes in PHASES.items():
        if any(path == p or (p.endswith("/") and path.startswith(p)) for p in prefixes):
            return phase
    return "Other"


def marker_lines(path, text):
    """Yield (line_no, line). In .py files, only comments and docstrings count, not code strings."""
    in_doc = False
    for n, line in enumerate(text.splitlines(), 1):
        if path.endswith(".py"):
            quotes = line.count('"""')
            counts = in_doc or ("#" in line and MARKER.search(line.split("#", 1)[1] or "")) or (quotes and MARKER.search(line))
            if quotes % 2 == 1:
                in_doc = not in_doc
            if not counts:
                continue
        if MARKER.search(line) or FILL_INS.search(line):
            yield n, line


def clean(line, width=170):
    s = re.sub(r"\s+", " ", line.strip().lstrip("#").lstrip("-").lstrip("|").strip())
    s = s.replace("|", "/")
    return s if len(s) <= width else s[: width - 1] + "…"


# ---------------- real-data scan ----------------

PHONE = re.compile(r"(?<![\w.])(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}(?!\d)|(?<![\w.-])\d{3}-\d{4}(?![\d])")
FICTIONAL_PHONE = re.compile(r"555[-. ]?01\d\d")          # NANP 555-0100..0199 is reserved for fiction
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SAFE_EMAIL = re.compile(r"@(example\.(com|org|net)|[\w.-]+\.(invalid|test|example))$|@anthropic\.com$|@users\.noreply\.github\.com$", re.I)
KEYS = [
    ("Anthropic-style key", re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}")),
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9]{20,}")),
    ("AWS access key", re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("Slack token", re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}")),
    ("Private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Generic secret assignment", re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\s*[=:]\s*['\"]?(?!fake-|replace-with|<)[A-Za-z0-9/_+=-]{24,}")),
]
CARD = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
KNOWN_TEST_CARDS = {"4111111111111111"}   # Visa's published test number


def scan(files):
    findings = []
    for path in files:
        # Skip this script and its own output: open-items.md quotes past findings,
        # so scanning it would re-flag those quotes on every rebuild.
        if path in SELF or path == "docs/open-items.md":
            continue
        try:
            text = (ROOT / path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for m in PHONE.finditer(line):
                num = m.group(0)
                if not FICTIONAL_PHONE.search(num) and not re.search(r"X{3}", num):
                    findings.append((path, n, "Phone-like number outside the fictional 555-01xx range", num))
            for m in EMAIL.finditer(line):
                if not SAFE_EMAIL.search(m.group(0)):
                    findings.append((path, n, "Email outside reserved example domains", m.group(0)))
            for label, rx in KEYS:
                for m in rx.finditer(line):
                    findings.append((path, n, label, m.group(0)[:12] + "…"))
            for m in CARD.finditer(line):
                digits = re.sub(r"\D", "", m.group(0))
                kind = "Card-like number (published TEST number)" if digits in KNOWN_TEST_CARDS else "Card-like number"
                findings.append((path, n, kind, m.group(0)))
    return findings


# ---------------- build ----------------

BLOCKERS = """\
These must be resolved before **any real client goes live**. Each is also in the full list below.

1. **Attorney review:** `docs/safety-and-compliance.md` (all of it, especially sections 3–4 and 14),
   `docs/service-agreement-outline.md` (especially **section 10a, emergency-paging liability**, and
   **section 6, what happens to emergency handling at a usage cap**), and all greeting and recording wording.
2. **Safety-expert review of the six Tier 1 lines** (`prompts/base_system_prompt.md` section 6, mirrored in `docs/call-flow.md` section 4).
3. **Default storage choice** (audio and/or transcripts). It drives the greeting's recording notice.
4. **Retention periods** (`data.retention_days` default, `MAX_RETENTION_DAYS`, log retention).
5. **Security contact:** replace `[EMAIL]` in `SECURITY.md`.
6. **SMS sender registration** for owner notifications (VERIFY, `docs/safety-and-compliance.md` section 4).
7. **Voice platform chosen**, plus real tool implementations with confirmed-delivery paging, retry, and backup (`docs/roadmap.md` section 1).
8. **Branch protection and the required CI check** on GitHub (manual, see the Phase 1 notes).
"""

RESOLVED = """\
- **Unit-economics doc drift (raised in Phase 8 review):** CI originally only ran the calculator (a smoke test).
  **Resolved in commit 5269ac1:** `docs/build_unit_economics_doc.py --check` regenerates the doc from the
  calculator's real output and fails on any difference. It runs in CI and in a pre-commit hook.
  Drift was tested by changing a default, and by hand-editing a number in the doc. Both were caught.
- **Prompt/call-flow drift, one-way Tier 1 check:** still open. See the TODO(me) in `tests/check_prompt_sync.py` below.
- **Real-format example values (found by the final scan):** `+1-312-867-5309`, `+1-312-555-0000`, and
  `+1-312-555-1234` (validator tests and an error message), `owner@acmehvac.com` (a test), and the
  company name "Top Rank Marketing" (scenario O01). These were invented examples, not client data, but
  real-looking numbers and domains can belong to real people. **Replaced** with fictional 555-01xx numbers,
  an `.invalid` address, and "Example Rank Marketing". The old values still exist in earlier commits
  `ab29fc8` and `7f13be5`. gitleaks found no secrets in any commit.
  - [ ] TODO(me): optionally rewrite history to drop them before the first push. Nothing has been pushed yet,
    so no one else has a copy. Not required: they aren't secrets or client data.
"""


def build():
    files = repo_files()
    by_phase = OrderedDict((p, OrderedDict()) for p in list(PHASES) + ["Other"])
    total_todo = total_verify = 0
    for path in files:
        if path in GENERATED or path in SELF:
            continue
        try:
            text = (ROOT / path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        items = list(marker_lines(path, text))
        if items:
            by_phase[phase_of(path)][path] = items
            for _, line in items:
                total_todo += len(re.findall(r"TODO\(me\)", line))
                total_verify += len(re.findall(r"VERIFY", line))

    out = [
        "# Open Items: master checklist before go-live",
        "",
        "<!-- GENERATED by docs/build_open_items.py. Don't edit by hand; rerun the script. -->",
        "",
        f"Generated {date.today().isoformat()} from every `TODO(me)`, `VERIFY`, and required fill-in "
        "(`[EMAIL]` and similar) in the repo. Regenerate after changes with:",
        "",
        "```bash\npython docs/build_open_items.py\n```",
        "",
        "Generated copies (`tests/scenarios.md`, `docs/unit-economics.md`) are skipped. Their sources are listed instead.",
        f"In Python files, only comments and docstrings count. **Totals: {total_todo} `TODO(me)`, {total_verify} `VERIFY`.**",
        "",
        "## Blockers before any real client",
        "",
        BLOCKERS,
        "## Resolved or partly resolved during review",
        "",
        RESOLVED,
        "## Summary by phase",
        "",
        "| Phase | Files | Lines with items |",
        "|---|---|---|",
    ]
    for phase, files_items in by_phase.items():
        if files_items:
            out.append(f"| {phase} | {len(files_items)} | {sum(len(v) for v in files_items.values())} |")
    out.append("")

    for phase, files_items in by_phase.items():
        if not files_items:
            continue
        out.append(f"## {phase}")
        out.append("")
        for path, items in files_items.items():
            out.append(f"### `{path}`")
            for n, line in items:
                out.append(f"- [ ] [L{n}]({'../' + path}#L{n}): {clean(line)}")
            out.append("")

    findings = scan(repo_files())
    out += ["## Final real-data scan", "",
            "A scan of every tracked or non-ignored file for phone numbers outside the fictional 555-01xx range, "
            "emails outside reserved example domains, API-key patterns, private-key blocks, and card-like numbers. "
            "Gitignored files (`.env`, `clients/*/private/`) are not read.", ""]
    if findings:
        out.append("| File | Line | Finding | Match |")
        out.append("|---|---|---|---|")
        for path, n, kind, match in findings:
            out.append(f"| `{path}` | {n} | {kind} | `{match}` |")
    else:
        out.append("**No findings.**")
    out.append("")
    return "\n".join(out), findings


def main():
    text, findings = build()
    if "--scan" in sys.argv:
        for path, n, kind, match in findings:
            print(f"{path}:{n}: {kind}: {match}")
        print(f"{len(findings)} finding(s)")
        return
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"Wrote docs/open-items.md ({len(findings)} scan finding(s))")


if __name__ == "__main__":
    main()
