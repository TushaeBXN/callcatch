# Roadmap

No dates, just the order of work.

## 1. After-hours receptionist (current)
Done in this repo: call flow, safety prompt, 41 test scenarios and the runner,
the fail-closed config validator, onboarding and offboarding, the agreement
outline, unit economics, and CI.

Still to do before the first pilot:
- [ ] Clear the blocking items in `docs/open-items.md` (attorney review, safety review of the Tier 1 wording, storage defaults)
- [x] Choose a voice platform: **Twilio** (`docs/decisions/0001-twilio-and-a2p-10dlc.md`)
- [ ] Build the Twilio voice adapter (`docs/architecture.md`)
- [ ] Build the real tool implementations: `save_message`, `notify_owner` (with confirmed delivery, retry, and backup), `check_or_book_slot`
- [ ] Start A2P 10DLC registration with Twilio now. It takes calendar time. TODO(me)
- [ ] Build the Twilio SMS adapter and the SMS half of `notify_owner`. Email stays a second channel.
- [ ] Monitoring and alerts (`docs/monitoring.md`), starting with the emergency path
- [ ] Staging number, then one pilot client via `docs/onboarding.md`

## 2. Bilingual support (Spanish)
- [ ] Write and review the Spanish fallback line (`languages.other_language_line`). This is still TODO(me) from Phase 3, and needs a fluent reviewer.
- [ ] Spanish conversation support for clients who add `es` to `languages.supported`, with English summaries to the owner
- [ ] Translate and review the Tier 1 safety lines, **word for word, fixed**, with the same drift check as English
- [ ] Spanish test scenarios

## 3. Simple client dashboard
- [ ] The owner sees their calls, summaries, and weekly report
- [ ] Read-only at first. Any settings change still goes through a validated config PR, or the same `config_schema.py` checks on the server.
- [ ] Per-client access control, with MFA

## 4. Sales follow-up / lead reactivation (later, don't build yet)
A separate product with heavier legal requirements (`docs/reactivation-later.md`):
- [ ] **A2P 10DLC registration** (US carrier registration for business texting): brand and campaign. VERIFY the current process.
- [ ] **Consent records** for every contact: proof of opt-in under the TCPA (the US law on automated calls and texts) and state law. VERIFY with an attorney.
- [ ] **Opt-out handling**: STOP honored immediately and permanently, across every channel
- [ ] Quiet hours and Do-Not-Call checks
- [ ] Its own agreement terms and compliance review

## Not planned
- Uncensored or "abliterated" models for anything customer-facing
- Cold calls or cold texts
- Pretending to be a human
