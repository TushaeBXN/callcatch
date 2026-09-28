# Safety and Compliance — CallCatch

> **DRAFT OUTLINE — NOT LEGAL ADVICE — FOR ATTORNEY REVIEW.**
> This document was drafted by a non-lawyer, with AI help, to organize questions
> and planned controls. Every legal statement marked `VERIFY:` may be incomplete,
> out of date, or wrong for a particular state. **No client goes live until a
> licensed attorney has reviewed this document**, the service agreement, and the
> greeting and recording wording.

- **Operator:** Anthos Intelligence Company
- **Service:** CallCatch, an inbound after-hours AI receptionist
- **Document owner:** TODO(me)
- **Last reviewed:** 2026-09-28 (draft). Attorney review: TODO(me)

---

## 1. Scope

This document covers the **receptionist** only: calls a business forwards to us.
It does not cover the future outbound reactivation product, which carries
separate and heavier requirements (see `docs/reactivation-later.md`).

---

## 2. AI disclosure

**Our policy:** every call starts by saying the caller is talking to an
automated assistant. If asked, the assistant always confirms that it is
automated. It never claims or implies that it is a person.

- Some states have laws about bots disclosing themselves, but their scope varies.
  Some only cover online bots, or bots used to sell something. VERIFY: which
  state laws apply to an inbound voice assistant.
- The FCC has said AI-generated voices count as "artificial" voices under the TCPA
  for **outbound** calls. VERIFY: current status and whether any part applies to
  inbound use.
- We disclose on every call regardless, because it's the honest default and it
  lowers risk whichever laws apply.

## 3. Call recording and transcription consent

**The problem:** callers can phone from anywhere. A caller in one state may reach a
business in another, and the stricter state's law may apply.

- US federal law is generally described as **one-party consent**: one person on the
  call can agree to recording. VERIFY.
- A number of states are commonly described as requiring **all-party consent**,
  meaning everyone on the call must agree. States often cited include California,
  Florida, Illinois, Maryland, Massachusetts, Montana, New Hampshire,
  Pennsylvania, and Washington, with others having partial or disputed rules
  (for example, Connecticut, Delaware, Michigan, Nevada, and Oregon).
  **VERIFY: this list is not authoritative.** An attorney must confirm it.
- **Is a transcript a "recording"?** Turning speech into text may be treated like
  recording under some laws. VERIFY.
- **Vendors listening in:** some lawsuits have argued that an AI or call-analytics
  vendor processing a call can count as a third party "eavesdropping", especially
  if the vendor may use call data for its own purposes, such as training.
  VERIFY: current case law, especially in California.

**Our planned controls:**
1. The recording notice is given on **every** call, before any information is
   collected, and it matches what we store ("recorded and transcribed" /
   "transcribed"). See `docs/call-flow.md` section 2.
2. Staying on the line after the notice is treated as consent. VERIFY: whether
   that is enough in every all-party state, or whether we need an explicit "is
   that okay?"
3. Variant C (no notice) is allowed only if no audio and no transcripts are stored.
   TODO(me): attorney to confirm.
4. We choose voice and LLM vendors whose terms say they **don't train on our call
   data**, and we record that in the vendor review (section 10). VERIFY each
   vendor's current terms.
5. The service agreement sets out who is responsible for disclosure and consent.
   See `docs/service-agreement-outline.md` (Phase 7).

## 4. Outbound contact and the TCPA

The **TCPA** (Telephone Consumer Protection Act) is the main US federal law about
automated calls and texts to consumers. VERIFY all points with an attorney.

- **The receptionist is inbound.** The caller phones the business. That is
  generally lower risk than outbound contact. VERIFY.
- **Owner notifications** (texts or emails to the business owner about their own
  calls) go to a business contact who asked for them. We record the owner's
  written opt-in during onboarding. VERIFY whether any consent formalities apply.
- **We do NOT send automated texts or calls to callers in version 1.** No
  "thanks for calling" texts, no reminders. A confirmation text to a consumer is
  outbound automated contact, and it can bring in TCPA consent rules and US
  carrier registration for business texting (A2P 10DLC).
- **The owner calling a customer back personally** after the customer asked for a
  callback is the business's own contact. VERIFY: confirm this is outside our
  responsibility and that the agreement says so.
- **No cold calls or cold texts. Ever.** Any outbound product needs documented
  prior consent, opt-out handling, quiet hours, and Do-Not-Call checks. TCPA
  consent rules changed in 2024–2025. VERIFY: current status before building
  anything outbound.

## 5. Data minimization

**We collect only what the owner needs to call back:** problem, callback number,
name, service address, urgency, and best callback time. We also collect caller
ID when the carrier provides it.

- The assistant never asks for payment details, account numbers, passwords,
  dates of birth, ID numbers, or health details. If a caller volunteers them, the
  assistant doesn't repeat them and tells the caller they aren't needed.
- Text-message summaries are kept short on purpose. Fuller details stay in email
  and in the access-controlled log.
- TODO(me): decide whether we automatically remove card-like numbers from
  transcripts before storing them.

## 6. Retention and deletion

| Data | Where | Kept for | Deleted how |
|---|---|---|---|
| Call summary (message) | Our store, per client | TODO(me) days | Automatic expiry |
| Transcript | Our store, per client | TODO(me) days | Automatic expiry |
| Audio recording (if kept) | Our store, per client | TODO(me) days, or don't keep it | Automatic expiry |
| Vendor-side logs (voice platform, LLM provider) | The vendor | Per the vendor's terms. VERIFY each one. | Vendor settings, and zero-retention options where offered |
| Owner notifications | The owner's phone and inbox | Out of our control | Explained to the owner at onboarding |

- If a client's agreement sets a shorter period, the shorter period wins.
- At offboarding: export (if the agreement requires it), then delete. See
  `docs/offboarding.md` (Phase 6).
- VERIFY: whether any state requires a **minimum** retention period for any of
  this data. That would be unusual here, but check.

## 7. Per-client data separation

- **One phone number per client.** The number tells us which client a call
  belongs to.
- **One config per client** in `clients/<name>/`. Real data only goes in
  `clients/<name>/private/`, which is gitignored.
- **Separate storage per client:** a separate database partition and storage
  prefix. The software refuses to read one client's data while handling another
  client's call.
- **The model only sees one client's config per call.** Other clients' data is
  never in its context, so it can't leak it.
- **Access:** team members get access only to the clients they work on.
  TODO(me): how we grant and review access.

## 8. Secrets handling

- Keys live in `.env` locally (gitignored) and in a managed secret store in the
  cloud (for example AWS Secrets Manager; see `docs/architecture.md`). Never in
  code, configs, chat, or tickets.
- The gitleaks pre-commit hook scans every commit. We also turn on GitHub secret
  scanning if it's available.
- Each environment (dev, staging, production) has its own keys.
- Each key has only the permissions it needs.
- Spend caps are set both in our code (`.env`) and in each vendor's console.
- A leaked key is rotated first, then cleaned up. See `SECURITY.md`.

## 9. Least-privilege tool access

**Least privilege** means each part of the system can do only what it must.

- The assistant has exactly **three tools**: `save_message`, `notify_owner`, and
  `check_or_book_slot`.
- **The backend enforces this, not just the prompt**, so it holds even if a
  caller tricks the model:

| Tool | Hard limit enforced in code |
|---|---|
| `save_message` | Writes only to the current client's store. It can't read, list, or delete. |
| `notify_owner` | **Has no "send to" field.** It sends only to the numbers and emails in the client config, and is rate-limited per call. |
| `check_or_book_slot` | Only reaches the current client's calendar. It can check and create, but not delete or edit other bookings. Disabled unless the config turns it on. |

- The model has no internet access, no code execution, no payments, and no call
  transfer.
- In the cloud, each function gets its own permissions (IAM role), covering only
  what it needs.

## 10. Model and vendor selection

- **Customer-facing model:** a mainstream hosted model with built-in safety
  training, from a provider with published usage policies. **Never** an
  uncensored, "abliterated", or "obliterated" model. Those have had their
  safety behavior deliberately removed, which weakens protection against
  manipulation and harmful output, and leaves no vendor accountability.
- **Vendor review checklist** (fill in for each vendor):

| Question | Voice platform | LLM provider | SMS/email sender |
|---|---|---|---|
| Does it train on our data? (We need: no) | VERIFY | VERIFY | VERIFY |
| How long does it keep data? | VERIFY | VERIFY | VERIFY |
| Is a data processing agreement (DPA) available? | VERIFY | VERIFY | VERIFY |
| Security certifications (e.g. SOC 2 report) | VERIFY | VERIFY | VERIFY |
| Subprocessors (other companies it passes data to) | VERIFY | VERIFY | VERIFY |
| Data location | VERIFY | VERIFY | VERIFY |
| Spend caps available? | VERIFY | VERIFY | VERIFY |

## 11. Emergency limitations

- CallCatch is **not** an emergency service and **not** a substitute for 911. The
  assistant directs callers in danger to 911 and pages the owner, but it can't
  guarantee the owner will answer, or that the caller will act.
- The Tier 1 safety wording is fixed for all clients, and it needs review by
  someone with safety expertise. TODO(me).
- The service agreement must say this clearly. See Phase 7.

## 12. Incidents and breach notification

- Our response plan: contain, rotate keys, assess, notify, and record the lessons.
  See `SECURITY.md`.
- State data-breach laws define "personal information" differently. Name, phone
  number, and address alone may or may not trigger notification duties, and
  transcripts could contain more than that. VERIFY: breach-notification duties,
  both ours and each client's, with an attorney.
- TODO(me): an incident log location and a notification contact list.

## 13. Control summary (for GRC review)

**GRC** (governance, risk, and compliance) reviewers look for each control, the
evidence it works, and who owns it. The mapping to the functions of the NIST
Cybersecurity Framework (CSF) 2.0 is approximate. VERIFY.

| ID | Control | Evidence | Owner | CSF 2.0 function |
|---|---|---|---|---|
| C-01 | AI disclosure on every call | Greeting in each config, plus test scenarios | Founder | Govern |
| C-02 | Recording notice matches what we store | Config field, plus a storage-settings review | Founder | Govern |
| C-03 | No automated outbound contact to consumers in v1 | Architecture doc, and no outbound code paths | Founder | Govern |
| C-04 | Data minimization (six fields) | Base prompt section 5, plus test scenarios | Prompt owner | Protect |
| C-05 | Retention limits and automatic deletion | Storage expiry settings | TODO(me) | Protect |
| C-06 | Per-client separation | One number and config per client, storage partitioning | TODO(me) | Protect |
| C-07 | Secret scanning and no secrets in git | gitleaks hook, GitHub scanning | All contributors | Protect |
| C-08 | Key rotation procedure | `SECURITY.md` | Founder | Respond |
| C-09 | Three-tool limit enforced in code | Backend code and tests | TODO(me) | Protect |
| C-10 | Prompt changes via PR plus a scenario review | `prompts/CHANGELOG.md`, PR history | Prompt owner | Govern |
| C-11 | Fixed Tier 1 emergency handling | Prompt, drift check, test scenarios | Founder | Protect |
| C-12 | Monitoring and weekly log review | `docs/monitoring.md` | TODO(me) | Detect |
| C-13 | Voicemail fallback on system failure | Fallback config, failure test scenario | TODO(me) | Recover |
| C-14 | Safety-trained hosted model only | Vendor review (section 10) | Founder | Govern |

## 14. Questions for the attorney

1. Is a notice at the start of the call, plus the caller staying on the line,
   enough consent for recording and transcription in every all-party-consent state?
2. Does transcription alone (no audio) count as recording?
3. Does using an AI vendor create third-party-eavesdropping risk, and what vendor
   terms reduce it?
4. Which state bot-disclosure laws apply to an inbound voice assistant?
5. Do any TCPA or state rules apply to our texts to business owners?
6. Who is responsible for disclosure and consent, us or the client? How should
   the agreement divide that?
7. What are our breach-notification duties, versus the client's, for this data?
8. What emergency-service disclaimers should the agreement and the greeting include?
9. What retention periods would you recommend?
