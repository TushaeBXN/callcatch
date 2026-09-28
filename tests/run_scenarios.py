"""
CallCatch scenario runner.

Plays each test call in tests/scenarios.yaml against the configured LLM
adapter, then writes a REVIEW SHEET for a human to grade. It does not
grade anything itself, because judging a phone conversation is subjective.

Usage (run from the repo root, with your virtual environment active):

    python tests/run_scenarios.py --dry-run           # no model calls, free: checks the plumbing
    python tests/run_scenarios.py --only E01 F01      # live run on just these scenarios
    python tests/run_scenarios.py --limit 5           # live run on the first 5
    python tests/run_scenarios.py --category prompt_injection

Which model is used comes from .env (LLM_PROVIDER, LLM_API_KEY, LLM_MODEL).
LLM_PROVIDER=stub uses a fake model with no network and no cost.

Output goes to tests/reports/<date-time>/ (gitignored):
    review.md   one section per call: transcript + checkboxes + PASS/FAIL line
    review.csv  one row per call, for a spreadsheet
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    import yaml
except ImportError:
    sys.exit("PyYAML isn't installed. Inside your virtual environment run: pip install pyyaml")

from backend.adapters import MissingSettingError, ToolResult, get_llm_adapter
from backend.prompt_builder import TEMPLATE_CONFIG, build_system_prompt, load_dotenv
from backend.tools import TOOLS

SCENARIOS_FILE = REPO_ROOT / "tests" / "scenarios.yaml"
REPORTS_DIR = REPO_ROOT / "tests" / "reports"
LIVE_CONFIRM_THRESHOLD = 5   # ask before live runs larger than this


# ---------- simulated tools ----------

def simulate_tool(name, arguments, simulate):
    """Return a fake result for a tool call. Scenarios can force failures via `simulate:`."""
    mode = (simulate or {}).get(name, "ok")
    if name == "notify_owner":
        status = {"ok": "delivered", "failed": "failed", "pending": "pending"}.get(mode, "delivered")
        return ToolResult(call_id="", content=json.dumps({"status": status}), is_error=(status == "failed"))
    if mode == "failed":
        return ToolResult(call_id="", content=json.dumps({"status": "failed"}), is_error=True)
    if name == "save_message":
        return ToolResult(call_id="", content=json.dumps({"status": "saved"}))
    if name == "check_or_book_slot":
        if arguments.get("action") == "book":
            return ToolResult(call_id="", content=json.dumps({"status": "booked", "slot_id": arguments.get("slot_id", "slot-1")}))
        return ToolResult(call_id="", content=json.dumps({"status": "available", "slots": [{"slot_id": "slot-1", "time": "Saturday 9am"}]}))
    return ToolResult(call_id="", content=json.dumps({"status": "unknown_tool"}), is_error=True)


# ---------- running one call ----------

def run_scenario(adapter, system_prompt, scenario, max_turns):
    """Play one scenario. Returns (transcript lines, token totals, notes)."""
    conversation, transcript = [], []
    tokens = {"input": 0, "output": 0}
    notes, model_turns = [], 0

    for caller_line in scenario["caller_script"]:
        shown = caller_line if caller_line else "[silence]"
        transcript.append(f"**Caller:** {shown}")
        conversation.append({"role": "user", "text": caller_line})

        # The model may call tools several times before it speaks.
        while True:
            if model_turns >= max_turns:
                notes.append(f"Stopped: reached MAX_LLM_TURNS_PER_CALL ({max_turns}).")
                return transcript, tokens, notes
            turn = adapter.respond(system_prompt, conversation, TOOLS)
            model_turns += 1
            tokens["input"] += turn.input_tokens
            tokens["output"] += turn.output_tokens

            conversation.append({"role": "assistant", "text": turn.text, "tool_calls": turn.tool_calls, "raw": turn.raw})
            if turn.text:
                transcript.append(f"**Assistant:** {turn.text}")
            if turn.stop_reason.startswith(("refusal", "max_tokens")):
                notes.append(f"Model stop reason: {turn.stop_reason}")
            if not turn.tool_calls:
                break

            results = []
            for call in turn.tool_calls:
                result = simulate_tool(call.name, call.arguments, scenario.get("simulate"))
                result.call_id = call.id
                results.append(result)
                transcript.append(
                    f"`TOOL {call.name}` args: `{json.dumps(call.arguments, ensure_ascii=False)}` "
                    f"-> result: `{result.content}`"
                )
            conversation.append({"role": "tool", "results": results})

    return transcript, tokens, notes


def dry_run_transcript(scenario):
    lines = [f"**Caller:** {line or '[silence]'}" for line in scenario["caller_script"]]
    lines.append("_(dry run: no model was called)_")
    return lines


# ---------- report writing ----------

def write_reports(out_dir, results, header):
    out_dir.mkdir(parents=True, exist_ok=True)
    md = [f"# Scenario Review Sheet\n", header, ""]
    md.append("**How to review:** read each transcript. Tick every expected behavior you see. "
              "Any 'must not do' that happened = FAIL. Write PASS or FAIL and a short note.\n")
    md.append("| ID | Category | Title | PASS/FAIL | Note |\n|---|---|---|---|---|")
    for r in results:
        s = r["scenario"]
        md.append(f"| {s['id']} | {s['category']} | {s['title']} |  |  |")
    md.append("")

    for r in results:
        s = r["scenario"]
        md.append(f"---\n\n## {s['id']} — {s['title']}\n")
        md.append(f"Category: `{s['category']}`" + (f" · Simulated: `{s['simulate']}`" if s.get("simulate") else ""))
        md.append("\n### Transcript\n")
        md.extend(f"{line}  " for line in r["transcript"])
        if r["notes"]:
            md.append("\n**Runner notes:** " + " ".join(r["notes"]))
        md.append("\n### Expected (tick what you saw)\n")
        md.extend(f"- [ ] {item}" for item in s["expected_behaviors"])
        md.append("\n### Must NOT do (any tick = FAIL)\n")
        md.extend(f"- [ ] {item}" for item in s["must_not_do"])
        md.append("\n**Result:** PASS / FAIL   **Reviewer:** ______   **Note:** ______\n")

    (out_dir / "review.md").write_text("\n".join(md), encoding="utf-8")

    with open(out_dir / "review.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "category", "title", "pass_fail", "reviewer", "note", "runner_notes"])
        for r in results:
            s = r["scenario"]
            writer.writerow([s["id"], s["category"], s["title"], "", "", "", " ".join(r["notes"])])


# ---------- main ----------

def load_scenarios(args):
    data = yaml.safe_load(SCENARIOS_FILE.read_text(encoding="utf-8"))
    scenarios = data["scenarios"]
    required = {"id", "category", "title", "caller_script", "expected_behaviors", "must_not_do"}
    for s in scenarios:
        missing = required - set(s)
        if missing:
            sys.exit(f"Scenario {s.get('id', '?')} is missing fields: {sorted(missing)}")
    ids = [s["id"] for s in scenarios]
    if len(ids) != len(set(ids)):
        sys.exit("Duplicate scenario IDs in scenarios.yaml.")

    if args.only:
        wanted = {i.upper() for i in args.only}
        unknown = wanted - set(ids)
        if unknown:
            sys.exit(f"Unknown scenario IDs: {sorted(unknown)}")
        scenarios = [s for s in scenarios if s["id"] in wanted]
    if args.category:
        scenarios = [s for s in scenarios if s["category"] == args.category]
    if args.limit:
        scenarios = scenarios[: args.limit]
    return scenarios


def main():
    parser = argparse.ArgumentParser(description="Run CallCatch test-call scenarios and build a review sheet.")
    parser.add_argument("--dry-run", action="store_true", help="No model calls. Builds the sheet from the scripts only.")
    parser.add_argument("--only", nargs="+", metavar="ID", help="Run only these scenario IDs, e.g. --only E01 F01")
    parser.add_argument("--category", help="Run only one category, e.g. prompt_injection")
    parser.add_argument("--limit", type=int, help="Run only the first N matching scenarios")
    parser.add_argument("--config", default=str(TEMPLATE_CONFIG), help="Client config to test with (default: the template)")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt for large live runs")
    args = parser.parse_args()

    load_dotenv()
    scenarios = load_scenarios(args)
    if not scenarios:
        sys.exit("No scenarios matched your filters.")
    system_prompt = build_system_prompt(Path(args.config))   # also checks the prompt markers

    provider = os.environ.get("LLM_PROVIDER", "stub").strip().lower()
    max_turns = int(os.environ.get("MAX_LLM_TURNS_PER_CALL", "30"))

    adapter = None
    if not args.dry_run:
        try:
            adapter = get_llm_adapter()
        except MissingSettingError as e:
            sys.exit(
                f"\nCan't start a live run: {e}\n\n"
                "What to do:\n"
                "  1. cp .env.example .env        (if you haven't already)\n"
                "  2. In .env, set LLM_PROVIDER=anthropic, LLM_API_KEY=<your key>, LLM_MODEL=<model name>\n"
                "  3. Or run for free with: python tests/run_scenarios.py --dry-run\n"
                "     (or LLM_PROVIDER=stub for a fake model)\n"
            )
        if provider != "stub" and len(scenarios) > LIVE_CONFIRM_THRESHOLD and not args.yes:
            answer = input(f"About to make LIVE, paid model calls for {len(scenarios)} scenarios. Continue? [y/N] ")
            if answer.strip().lower() != "y":
                sys.exit("Cancelled. Tip: start with --only or --limit 3.")

    mode = "DRY RUN" if args.dry_run else f"provider={provider}" + (f", model={getattr(adapter, 'model', '')}" if getattr(adapter, "model", "") else "")
    print(f"Running {len(scenarios)} scenario(s) [{mode}]")

    results, totals = [], {"input": 0, "output": 0}
    for s in scenarios:
        print(f"  {s['id']:4} {s['title']}")
        if args.dry_run:
            results.append({"scenario": s, "transcript": dry_run_transcript(s), "notes": []})
            continue
        try:
            transcript, tokens, notes = run_scenario(adapter, system_prompt, s, max_turns)
        except Exception as e:   # keep going; record the error for the reviewer
            transcript, tokens, notes = [f"**Caller:** {s['caller_script'][0]}"], {"input": 0, "output": 0}, [f"ERROR: {type(e).__name__}: {e}"]
            print(f"       error: {type(e).__name__}")
        totals["input"] += tokens["input"]
        totals["output"] += tokens["output"]
        results.append({"scenario": s, "transcript": transcript, "notes": notes})

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_dir = REPORTS_DIR / (stamp + ("_dry-run" if args.dry_run else ""))
    header = (f"- Run: {stamp} · Mode: {mode} · Scenarios: {len(results)}\n"
              f"- Prompt: prompts/base_system_prompt.md · Config: {Path(args.config).relative_to(REPO_ROOT) if Path(args.config).is_absolute() else args.config}\n"
              f"- Tokens used: {totals['input']} input, {totals['output']} output (check your provider's console for cost)")
    write_reports(out_dir, results, header)
    print(f"\nDone. Review sheet: {out_dir.relative_to(REPO_ROOT)}/review.md")
    if not args.dry_run:
        print(f"Tokens used: {totals['input']} input, {totals['output']} output")


if __name__ == "__main__":
    main()
