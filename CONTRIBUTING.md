# Contributing to CallCatch

Welcome! This guide assumes you're new to git and GitHub. If anything here is
confusing, ask. That's normal, and it helps us fix the guide.

## The big picture (in plain English)

- `main` is the official copy of the project. **Nobody edits `main` directly.**
- To change something, you make your own **branch**, a separate copy where you
  can work without affecting anyone else.
- When you're done, you open a **pull request (PR)**, which asks the team:
  "please review my change and merge it into `main`."
- Someone reviews it. Once the checks pass and it's approved, it gets merged.

## Step by step

```bash
git checkout main
```
Switches to the main branch.

```bash
git pull
```
Downloads the latest changes so you start from an up-to-date copy.

```bash
git checkout -b docs/fix-onboarding-typo
```
Creates your new branch and switches to it. See the naming rules below.

Make your edits, then:

```bash
git status
```
Shows which files you changed. Check that no `.env`, key, or client data file is listed.

```bash
git add docs/onboarding.md
```
Stages the specific files you want to commit. Name files one at a time instead of using `git add .`.

```bash
git commit -m "Fix typo in onboarding checklist"
```
Saves a snapshot with a short message. The gitleaks secret scan runs automatically here.

```bash
git push -u origin docs/fix-onboarding-typo
```
Uploads your branch to GitHub. Then open a PR on GitHub and fill in the checklist.

## Branch naming

Use `type/short-description`, lowercase, with dashes:

| Prefix | Use for | Example |
|---|---|---|
| `docs/` | Documentation | `docs/add-carrier-guide` |
| `prompt/` | Changes to anything in `prompts/` | `prompt/tighten-price-refusal` |
| `test/` | New or changed test scenarios | `test/add-co-alarm-case` |
| `client/` | A client config change | `client/acme-hvac-hours` |
| `feat/` | New code features | `feat/email-notifier` |
| `fix/` | Bug fixes | `fix/runner-missing-key-msg` |

## One person owns each client folder

Each `clients/<name>/` folder has **one owner**, named in the config's
changelog section. Only that owner edits it, or approves someone else's PR
that touches it. This prevents two people changing a live client's setup at
the same time. TODO(me): decide how ownership is recorded and handed over.

## Required before merge

A PR can merge into `main` only when:

- [ ] At least one other person has reviewed and approved it.
- [ ] The gitleaks secret scan passes.
- [ ] **If you changed `prompts/`:** you ran the test scenarios
      (`tests/run_scenarios.py`), attached or summarized the review sheet, and
      updated `prompts/CHANGELOG.md`.
- [ ] **If you changed a client config:** the folder owner approved it, and
      the config's changelog section is updated.
- [ ] No real names, phone numbers, addresses, keys, transcripts, or recordings.

## Golden rules

- Never commit `.env`, keys, or anything from `clients/*/private/`.
- Use fake data only: `Acme HVAC`, `+1-555-0100`, `123 Example St`.
- If you commit a secret by accident, **tell the maintainer immediately**
  and follow "If a key leaks" in [SECURITY.md](SECURITY.md). No blame; speed matters.
- Small PRs are better than big ones. They're easier to review and safer.
