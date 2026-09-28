"""
Builds docs/unit-economics.md from docs/templates/unit-economics.md.tmpl, using
the calculator's REAL output, so the doc can't drift from the code.

    python docs/build_unit_economics_doc.py           # rewrite the doc
    python docs/build_unit_economics_doc.py --check   # exit 1 if the doc is stale (CI and pre-commit)

Standard library only.
"""

import difflib
import json
import subprocess
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent
# Every number comes from RUNNING the calculator (never importing it), so a
# stale __pycache__ can't make the doc disagree with the code.

TEMPLATE = DOCS / "templates" / "unit-economics.md.tmpl"
OUTPUT = DOCS / "unit-economics.md"
SCRIPT = DOCS / "unit_economics.py"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def build() -> str:
    example = run()
    if example.returncode != 0:
        sys.exit(f"Calculator failed:\n{example.stderr}")
    above = run("--calls-per-week", "60", "--avg-job-value", "250").stdout
    above = above[above.index("OUTPUTS"):above.index("SENSITIVITY")].rstrip()
    bad = run("--calls-per-week", "0", "--telephony-per-min", "-0.01")
    if bad.returncode != 1:
        sys.exit("Expected the invalid-input example to be rejected (exit 1), but it wasn't.")

    data = json.loads(run("--json").stdout)
    d, r, wpm = data["inputs"], data["outputs"], data["weeks_per_month"]
    values = {
        "{EX}": example.stdout.rstrip(),
        "{ABOVE}": above,
        "{BAD}": bad.stderr.rstrip(),
        "{CALLS_WEEK}": f"{d['calls_per_week']:g}",
        "{MONTHLY_COST}": f"${r['monthly_cost']:,.0f}",
        "{RETAINER}": f"${d['monthly_retainer']:,.0f}",
        "{MARGIN_PCT}": f"{r['monthly_margin_pct']:.1f}%",
        "{MIN_MARGIN}": f"{d['min_margin_pct']:g}%",
        "{CAP_WEEK}": f"{float(r['cap_point_calls_per_month']) / wpm:,.0f}",
        "{BE_WEEK}": f"{float(r['break_even_calls_per_month']) / wpm:,.0f}",
    }
    text = TEMPLATE.read_text(encoding="utf-8")
    for key, val in values.items():
        if key not in text:
            sys.exit(f"Template is missing placeholder {key}")
        text = text.replace(key, val)
    return text


def main():
    fresh = build()
    if "--check" in sys.argv:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != fresh:
            diff = difflib.unified_diff(current.splitlines(), fresh.splitlines(),
                                        "committed docs/unit-economics.md", "fresh output", lineterm="", n=1)
            print("docs/unit-economics.md is STALE. It no longer matches the calculator's output:\n")
            print("\n".join(list(diff)[:40]))
            print("\nFix: python docs/build_unit_economics_doc.py   (then commit the updated doc)")
            sys.exit(1)
        print("OK: docs/unit-economics.md matches the calculator's current output.")
        return
    OUTPUT.write_text(fresh, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(DOCS.parent)}")


if __name__ == "__main__":
    main()
