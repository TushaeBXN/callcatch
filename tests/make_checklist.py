"""
Regenerates tests/scenarios.md (the human-readable checklist) from
tests/scenarios.yaml, so the two never drift apart.

Run after editing scenarios.yaml:   python tests/make_checklist.py
Never edit scenarios.md by hand.
"""

import sys
from collections import Counter
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML isn't installed. Inside your virtual environment run: pip install pyyaml")

ROOT = Path(__file__).resolve().parent
scenarios = yaml.safe_load((ROOT / "scenarios.yaml").read_text(encoding="utf-8"))["scenarios"]

out = [
    "# Test-Call Scenarios (checklist)",
    "",
    "> Generated from `scenarios.yaml` by `make_checklist.py`. **Don't edit by hand.**",
    "",
    f"**{len(scenarios)} scenarios.** Coverage by category:",
    "",
    "| Category | Count |",
    "|---|---|",
]
for cat, n in sorted(Counter(s["category"] for s in scenarios).items()):
    out.append(f"| {cat} | {n} |")
out.append("")

for s in scenarios:
    out.append(f"## {s['id']} — {s['title']}")
    out.append(f"*Category:* `{s['category']}`" + (f" · *Simulated:* `{s['simulate']}`" if s.get("simulate") else ""))
    out.append("")
    out.append("**Caller says:**")
    out.extend(f"{i}. {line or '[silence]'}" for i, line in enumerate(s["caller_script"], 1))
    out.append("")
    out.append("**Expected:**")
    out.extend(f"- [ ] {b}" for b in s["expected_behaviors"])
    out.append("")
    out.append("**Must NOT:**")
    out.extend(f"- [ ] {b}" for b in s["must_not_do"])
    out.append("")

(ROOT / "scenarios.md").write_text("\n".join(out), encoding="utf-8")
print(f"Wrote tests/scenarios.md ({len(scenarios)} scenarios)")
