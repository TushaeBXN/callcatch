# CallCatch

**An AI receptionist that answers the calls your business misses after hours — and never lets an emergency slip through.**

CallCatch picks up when a local service business is closed. It talks to the caller, takes down what they need, and gets the message to the right person immediately. If the call is a genuine emergency — a gas leak, a fire, a flood near live electrics — it recognizes that within the first few words and pages the on-call number right away, before it finishes talking to the caller.

It is not a chatbot bolted onto a phone line. It is a small, carefully constrained system: three tools, a fixed set of safety rules that no client configuration can override, and a test suite that has to pass before any client goes live.

---

## What it actually does

**For every after-hours call, it:**
1. Answers immediately and discloses that it's an automated assistant (and that the call is recorded, if it is).
2. Listens for what's wrong, the caller's name, a callback number (read back to confirm), the service address, and the best time to call back.
3. Watches for emergencies from the first sentence of the call, not just when asked.
4. If it's a real emergency, gives the caller a safety instruction (get outside, call 911) and pages the business's on-call number immediately — before finishing the conversation.
5. Sends the business owner a text or email summary of every call, and a separate priority alert for anything urgent.
6. Falls back cleanly to plain voicemail if anything in the pipeline fails, so a caller never gets dead air.

**What it will never do:**
- Quote a price, promise an arrival time, or give repair or diagnostic advice.
- Pretend to be a person, the owner, or anyone else.
- Let a caller talk it into ignoring its instructions, revealing its setup, or treating them as "the owner" or "the police" without any actual verification.
- Tell a caller something isn't an emergency, or tell them not to call 911.

---

## Why this matters for a small business

A missed call after hours is a lost job. A homeowner with a burst pipe at 9pm calls the next name on Google if nobody answers. Most service businesses have no good way to catch that — a human answering service is expensive and slow to set up, and most owners are wary of "AI" doing something as sensitive as talking to their customers about an emergency in their home.

CallCatch is built around that hesitation, not around ignoring it:
- **Every emergency line is fixed and disclosed.** The business can't accidentally weaken the safety wording, and neither can we — it's enforced in code, not just written in a policy doc.
- **The business approves the emergency contacts and wording in writing before going live.**
- **Every call is disclosed as automated**, with a recording notice that matches what's actually stored.
- **Nothing customer-facing runs on an unrestricted model.** It uses a mainstream, safety-trained model as a second layer of defense on top of the rules above.

The result: an owner gets a tool that catches lost jobs and handles genuine emergencies safely, without having to trust an AI's judgment on where the line is — because the line is fixed before the tool is ever turned on.

---

## Who this is for

Built for local, appointment- and dispatch-based service businesses where a missed after-hours call is a missed job, and where some calls are genuinely time-sensitive:

- **HVAC** — no heat/no cooling calls, especially with vulnerable occupants
- **Plumbing** — burst pipes, leaks near electrical, sewage backups
- **Electrical** — sparking, burning smells, panel issues
- **Roofing** — active leaks during storms
- **Garage doors** — stuck-open doors (security risk), trapped vehicles
- **Auto repair / roadside** — breakdowns, especially in unsafe locations
- **Gutter cleaning and other home-service trades** — lower urgency, but still benefits from lead capture and after-hours coverage

It's a poor fit for businesses where "emergency" doesn't mean physical danger (most retail, most professional services) — the safety-tier logic is the core of the product, and it's overkill where there's nothing dangerous to detect.

---

## How it's built (short version)

- **Prompt-based, not fine-tuned.** One fixed system prompt encodes the role, the safety tiers, and the tool rules. Per-client differences live in a config file, which is validated against a schema before it can ever reach the model.
- **Defense in depth.** The prompt tells the model what to do; the backend enforces it independently (the notification tool can't be redirected, the config can't remove a Tier 1 safety line, the model never even sees the client's real phone numbers or emails).
- **Tested before any client goes live.** A scenario suite covers normal calls, all six Tier 1 emergencies, angry/rambling/silent callers, prompt-injection attempts, and what happens when the paging system itself fails.
- **A drift check keeps the safety wording honest.** The emergency instructions exist in two places (the human-readable call-flow doc and the model's prompt) and a script fails the build if they ever stop matching word-for-word.

See `docs/architecture.md` for the full pipeline and `docs/call-flow.md` for exactly what a caller hears.

---

## Status

This is a working design with enforced safety rules and a full test harness — **not yet connected to a real phone line or a live model.** See `docs/open-items.md` for what's left before any real client goes live, starting with attorney review of the service agreement and expert review of the emergency wording.

---

## Project structure

```
prompts/           the model's fixed instructions
backend/            config schema, validator, tool definitions, adapters
clients/            one config file per business (real contact info kept separate and gitignored)
tests/              scenario suite, drift checks, validator tests
docs/               call flow, safety & compliance, onboarding/offboarding, service agreement outline, unit economics
```

---

## For contributors

Operated by Anthos Intelligence Company. Read [CONTRIBUTING.md](CONTRIBUTING.md)
and [SECURITY.md](SECURITY.md) first. All changes go through pull requests, and
no real client data, keys, or recordings ever go in git.

**Not built yet:** sales follow-up and reactivation of old leads. See
[docs/reactivation-later.md](docs/reactivation-later.md).

### Markers you'll see

- `TODO(me):` — a decision or fill-in the founder must make.
- `VERIFY:` — a fact that may be out of date (pricing, laws, carrier codes).
  Don't treat it as settled until someone checks.

All of them are collected in [docs/open-items.md](docs/open-items.md).

### Getting started

You need Python 3.12 or newer, **stable release** (not a beta or "rc").
VERIFY: check the current stable version at python.org.

> **macOS + python.org Python:** if you see `CERTIFICATE_VERIFY_FAILED`, run the
> `Install Certificates.command` file in your `/Applications/Python 3.x/`
> folder once. It installs the certificate list Python needs to trust websites.

One-time setup, run from inside the `callcatch` folder:

```bash
python3 -m venv .venv
```
Creates a private Python environment in `.venv/` so installs don't touch your system.

```bash
source .venv/bin/activate
```
Turns that environment on for this terminal window.

```bash
pip install -r requirements.txt
```
Installs the YAML reader, the pre-commit tool, and the Anthropic SDK (only needed for live test runs).

```bash
pre-commit install
```
Turns on the checks that run on every commit: the secret scan, the prompt drift check, config validation, and the unit-economics doc check.

```bash
cp .env.example .env
```
Creates your local settings file. Fill it in and never commit it.

### Every time you open a new terminal window

A new window starts in your home folder with the environment turned off.
Before running any project command, your prompt should look like
`(.venv) ... callcatch %`. If it doesn't:

```bash
cd ~/callcatch
```
Moves into the project folder (adjust the path if you cloned it elsewhere).

```bash
source .venv/bin/activate
```
Turns the environment back on.

`command not found: pre-commit` almost always means one of those two steps was skipped.

Note: `pre-commit run --all-files` only scans files git is tracking. In a brand-new
repo with nothing added yet, it says "no files to check". That's normal.
