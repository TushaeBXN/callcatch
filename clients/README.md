# Clients

Each client business gets its **own folder** here, and its **own phone number**.

```
clients/
  _template/            <- the starting point. Copy it, never edit it for a client.
    config.yaml
  acme-hvac/            <- one folder per client (folder name = client_id)
    config.yaml         <- settings, tracked in git, FAKE or PRIVATE contact values only
    private/            <- gitignored, never uploaded. Real contact details live here.
      contacts.yaml
```

## Rules

1. **One folder, one owner.** Each client folder has one owner (`folder_owner`
   in its config). Only the owner edits it or approves PRs that touch it. See
   CONTRIBUTING.md.
2. **One number and one config per client.** Never share either between clients.
3. **No real contact details in git.** In `config.yaml`, phone numbers must be
   fake (`+1-555-01xx`) or the word `PRIVATE`, and emails must be `@example.com`
   or `PRIVATE`. Real values go in `private/contacts.yaml`, which is
   gitignored (see `.gitignore`: `clients/*/private/`).
4. **Every change gets a changelog entry** at the bottom of that client's config.
5. **Safety rules aren't configurable.** A config can't change the Tier 1
   emergency list, the 911 instructions, the automated-assistant disclosure, or
   the recording notice rules. It can **add** emergency triggers (Tier 1 or 2)
   and set on-call numbers.

## Adding a client

```bash
cp -r clients/_template clients/acme-hvac
```
Copies the template into a new folder. Use the client's short name, lowercase with dashes.

Then edit `clients/acme-hvac/config.yaml`: set `client_id: acme-hvac`, fill in
every field, and replace every `TODO(me)`.

```bash
mkdir clients/acme-hvac/private
```
Creates the private folder. Git ignores it automatically.

Put real contact details in `clients/acme-hvac/private/contacts.yaml`. Only
these keys are allowed:

```yaml
agent_number: "+1-XXX-XXX-XXXX"
on_call_number: "+1-XXX-XXX-XXXX"
backup_on_call_number: "+1-XXX-XXX-XXXX"
sms_to: ["+1-XXX-XXX-XXXX"]
email_to: ["owner@their-real-domain"]
```

In `config.yaml`, write `PRIVATE` for each of those fields.

```bash
python tests/validate_config.py
```
Checks every client config. Fix any `ERROR` line. Warnings don't block.

```bash
git status
```
Before committing, confirm that nothing under `private/` is listed.

## Where validation runs

The same rules (`backend/config_schema.py`) run in four places, so there's no
path for a bad config to slip through:

| Where | When |
|---|---|
| Pre-commit hook | On your machine, when you commit a config change |
| GitHub CI (`.github/workflows/checks.yml`) | On every pull request, whoever made the change |
| Test runner / prompt builder | Refuses to build a prompt from an invalid config |
| Deploy (later) | `python tests/validate_config.py --require-private` also checks that every PRIVATE value exists |

## What the AI sees

Only the fields marked `[AI SEES THIS]` in the template: business facts, the
greeting, recording settings, languages, extra emergency triggers, approved
pricing wording, and whether booking is on. Phone numbers, emails, approvals,
retention, and notes are **never** sent to the model, so a caller can't talk
it into revealing them.
