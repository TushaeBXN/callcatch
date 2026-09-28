"""
Drift check: fails if the safety wording in the prompt and in the call-flow
document stop matching.

It checks:
  1. The six Tier 1 safety lines in docs/call-flow.md appear word for word in
     prompts/base_system_prompt.md.
  2. Every Tier 2 caller question in docs/call-flow.md (including the roof-leak
     electrics question and both no-heat questions) appears word for word in the prompt.
  3. The roof-leak electrics question and both no-heat questions are present,
     so deleting a row can't silently pass.

Run it from the repo root:   python tests/check_prompt_sync.py
Exit code 0 = in sync, 1 = drift found. Stdlib only, no installs needed.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CALL_FLOW = ROOT / "docs" / "call-flow.md"
PROMPT = ROOT / "prompts" / "base_system_prompt.md"

EXPECTED_TIER1_COUNT = 6
MUST_HAVE_QUESTIONS = [
    "Is the water near any outlets, electrical panels, or appliances?",   # leaks and roof
    "Is anyone elderly, a baby, or unwell in the home?",                 # no heat / cooling, Q1
    "Is anyone feeling sick right now?",                                 # no heat / cooling, Q2
]


def section(text, start_marker, end_marker):
    start = text.index(start_marker)
    return text[start: text.index(end_marker, start)]


def main():
    call_flow = CALL_FLOW.read_text(encoding="utf-8")
    prompt_full = PROMPT.read_text(encoding="utf-8")
    prompt = prompt_full.split("<!-- BEGIN PROMPT -->", 1)[1].split("<!-- END PROMPT -->", 1)[0]
    problems = []

    # 1. Tier 1: second column of the Tier 1 table, the first quoted sentence(s)
    tier1 = section(call_flow, "**Tier 1", "**Tier 2")
    tier1_lines = re.findall(r'^\| [^|]+ \| "(.+?)"', tier1, re.M)
    if len(tier1_lines) != EXPECTED_TIER1_COUNT:
        problems.append(f"Expected {EXPECTED_TIER1_COUNT} Tier 1 lines in call-flow.md, found {len(tier1_lines)}.")
    for line in tier1_lines:
        if f'"{line}"' not in prompt:
            problems.append(f'Tier 1 line not found word for word in the prompt: "{line}"')

    # 2. Tier 2: every quoted question in the Tier 2 table's question column
    tier2 = section(call_flow, "**Tier 2", "**Tier 3")
    tier2_questions = []
    for row in re.findall(r"^\|(.+)\|$", tier2, re.M):
        cells = [c.strip() for c in row.split("|")]
        if len(cells) >= 2:
            tier2_questions += re.findall(r'"([^"]+\?)"', cells[1])
    for q in tier2_questions:
        if f'"{q}"' not in prompt:
            problems.append(f'Tier 2 question in call-flow.md not found in the prompt: "{q}"')

    # 3. Required questions must exist in BOTH files
    for q in MUST_HAVE_QUESTIONS:
        for name, text in (("call-flow.md", tier2), ("base_system_prompt.md", prompt)):
            if f'"{q}"' not in text:
                problems.append(f'Required question missing from {name}: "{q}"')

    print(f"Checked {len(tier1_lines)} Tier 1 lines and {len(tier2_questions)} Tier 2 questions.")
    if problems:
        print("\nDRIFT FOUND:")
        for p in problems:
            print(f"  - {p}")
        print("\nFix: make docs/call-flow.md section 4 and prompts/base_system_prompt.md section 6 match, in the same PR.")
        sys.exit(1)
    print("OK: prompt and call-flow safety wording are in sync.")


if __name__ == "__main__":
    main()
