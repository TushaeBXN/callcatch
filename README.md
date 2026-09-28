# CallCatch

An automated after-hours receptionist for local service businesses: HVAC,
plumbing, roofing, garage doors, auto repair, and gutter cleaning.

Operated by Anthos Intelligence Company.

## What it does

1. After hours, the business forwards its phone line to a CallCatch number.
   **Call forwarding** means the phone company sends calls on to another number.
2. An automated assistant answers. It says it's automated, then collects the
   caller's name, callback number, address, and problem.
3. If the caller describes an emergency (a gas smell, flooding, and so on), the
   assistant gives safety instructions and pages the owner right away.
4. After the call, the owner gets a text or email summary.
5. Optionally, the assistant can check or book a calendar slot.

**Not built yet:** sales follow-up and reactivation of old leads. See
[docs/reactivation-later.md](docs/reactivation-later.md).

## Design principles

- **Safety first.** The customer-facing model is a mainstream hosted model with
  built-in safety training. We never use uncensored or modified models.
- **Vendor-neutral.** The voice platform and the LLM (large language model, the
  AI that writes replies) sit behind thin **adapters**, small wrapper modules, so
  either one can be swapped without rewriting the app.
- **Three tools only.** The assistant can `save_message`, `notify_owner`, and
  `check_or_book_slot`. Nothing else.
- **No real data in git.** See [SECURITY.md](SECURITY.md).

## Repo map

| Folder / file | What's in it |
|---|---|
| `clients/` | One folder per client. `_template/` is the starting point. |
| `prompts/` | The assistant's instructions (system prompt) and their changelog. |
| `backend/` | Application code, including the LLM and voice adapters. |
| `tests/` | Test-call scenarios and the scenario runner. |
| `infra/` | Optional cloud deployment files (later). |
| `docs/` | Call flow, safety, onboarding, economics, and more. |
| `docs/open-items.md` | Every `TODO(me):` and `VERIFY:` in one list. |

## Markers you'll see

- `TODO(me):` — a decision or fill-in the founder must make.
- `VERIFY:` — a fact that may be out of date (pricing, laws, carrier codes).
  Don't treat it as settled until someone checks.

## Getting started (for contributors)

Read [CONTRIBUTING.md](CONTRIBUTING.md) first.

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
pip install pyyaml pre-commit
```
Installs the YAML reader and the pre-commit tool.

```bash
pre-commit install
```
Turns on the secret-scanning check that runs on every commit.

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
