# Prompt Changelog

Every change to anything in `prompts/` is recorded here. The prompt is the most
safety-sensitive file in the repo. A one-word edit can change how the assistant
handles an emergency, so we treat it like code.

## How versioning works

Versions look like `MAJOR.MINOR.PATCH`, for example `1.4.2`.

| Bump | When | Examples |
|---|---|---|
| **MAJOR** | Changes to safety rules, emergency handling, tools, or the order of authority | Adding a Tier 1 item, adding a tool, changing the status-line rule |
| **MINOR** | Behavior changes that don't touch safety | New edge-case handling, a new collection step, tone changes |
| **PATCH** | Wording fixes that shouldn't change behavior | Typos, clearer phrasing of a non-safety line |

When in doubt, bump the higher one.

## Rules for every prompt change

1. **One PR per change**, on a `prompt/` branch (see CONTRIBUTING.md).
2. **Update the version** at the top of `base_system_prompt.md` and add an entry below.
3. **Run all test scenarios** with `tests/run_scenarios.py` (Phase 4) and fill in the
   review sheet. Every scenario must be reviewed. Summarize the results in the PR:
   how many passed, how many failed, and what you fixed.
4. **Tier 1 wording** must stay word for word identical to `docs/call-flow.md`
   section 4. Change both in the same PR. The drift-check script (Phase 4) must pass.
5. **MAJOR changes** need approval from the founder, not just any reviewer.
   TODO(me): confirm who can approve MAJOR prompt changes.
6. **Never** paste real caller transcripts into a PR or this file. Describe the
   problem using fake details instead.

## Entry format

```
## [version] — YYYY-MM-DD — short title
- What changed:
- Why: (link the failed scenario or log review that prompted it)
- Scenarios reviewed: N/N, failures: ...
- Approved by:
```

---

## [0.1.1] — 2026-09-28 — Review fixes before Phase 3 approval
- What changed:
  - Roof leak: always ask the electrical-proximity question. Yes or unclear is Tier 1.
  - No heat or cooling: always ask both vulnerability questions, in a fixed order.
  - Greeting: the config greeting must include the AI disclosure and a recording
    notice that matches storage. The voice platform may play it. The backend or CI
    must reject configs without it.
  - Call ending: the platform ends calls (after the goodbye, a silence timeout, or
    the maximum length). No end-call tool, so there are still exactly three tools.
  - Untrusted input: command-like caller text is recorded as quoted speech.
  - Health details: not asked for. Only an urgency flag is recorded, never
    conditions or medications.
  - Human notes: notify_owner succeeds only on confirmed delivery, and summary
    fields are untrusted text.
- Why: founder review of 0.1.0.
- Tier 1 lines: unchanged, and still identical to docs/call-flow.md.
- Scenarios reviewed: not yet (Phase 4).
- Approved by: founder (pending commit).

## [0.1.0] — 2026-09-28 — Initial draft
- What changed: first version of the base prompt, built from `docs/call-flow.md` as approved in Phase 2.
- Why: project start.
- Scenarios reviewed: not yet. The test scenarios arrive in Phase 4.
- Approved by: pending founder review.
