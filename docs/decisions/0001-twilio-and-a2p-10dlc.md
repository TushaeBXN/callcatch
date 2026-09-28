# Decision 0001: Twilio for voice and SMS; register for A2P 10DLC now

- **Date:** 2026-09-28
- **Status:** Accepted. Registration not yet started.
- **Decided by:** founder

A **decision record** is a short note of what we chose and why, so later
contributors don't reopen the question without knowing the reasoning.

## Decision

1. **Twilio** is our first voice and SMS platform.
2. We **treat A2P 10DLC registration as required** for owner notification texts
   (A2P 10DLC is US carrier registration for business texting from standard
   10-digit numbers), and start it now rather than waiting to find out whether
   owner-only alerts need it.
3. **Email stays a second notification channel for every client** (`notifications.channel: both`),
   so emergency alerts still arrive if SMS registration is delayed or a text is filtered.

## Why

- **Twilio:** voice, SMS, and registration live in one account, and it has the
  most beginner-facing documentation, which suits a team learning as it builds.
  Vonage is a reasonable second choice. VERIFY: current features and pricing
  before committing spend (`docs/unit_economics.py` inputs).
- **Register regardless:** if we assume registration isn't needed and we're
  wrong, the failure is carriers silently filtering our texts, and the text most
  likely to be lost is an emergency page, discovered only when one doesn't
  arrive. Registering when it wasn't strictly needed costs a fee and some time.
  That asymmetry decides it.
- **Start now:** registration review takes calendar time (VERIFY: current
  timelines), so starting while we build keeps it off the critical path to the
  first pilot.

## What this does NOT change

- **The adapters stay vendor-neutral.** Twilio code goes behind the voice and
  notification adapters (`docs/architecture.md`). Nothing outside `backend/adapters/`
  imports a vendor SDK.
- **"Alerted" still means confirmed delivery.** An accepted or queued Twilio
  message is not success. VERIFY: which delivery-status updates Twilio provides
  for SMS and calls, and how the backend receives them.

## Next steps

| Step | Owner | Status |
|---|---|---|
| Create the Twilio account under Anthos Intelligence Company, with MFA and a spend limit | Founder | TODO(me) |
| Register the brand and campaign for A2P 10DLC. Choose the use case closest to operational alerts to a business owner, never marketing. VERIFY: Twilio's current use-case names, required business details (e.g. EIN), fees, and review times. | Founder | TODO(me) |
| Build the Twilio SMS notification adapter and the SMS half of `notify_owner` (confirmed delivery, retry, backup) against test credentials | Tech | Not started |
| Keep `notifications.channel: both` in every client config (the validator warns on SMS-only) | Folder owners | In place |
