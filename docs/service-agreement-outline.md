# Service Agreement: Outline

> **DRAFT OUTLINE — NOT LEGAL ADVICE — FOR ATTORNEY REVIEW.**
> Written by a non-lawyer, with AI help, to organize business terms and
> questions for an attorney. This is **not** contract language and must not be
> sent to a client or signed in this form. Every `VERIFY:` is an assumption to
> check. Every `TODO(me)` is a business decision. Items marked **ATTORNEY** are
> questions only an attorney can answer.

- **Provider:** Anthos Intelligence Company ("we"), operating CallCatch
- **Client:** [CLIENT BUSINESS NAME] ("client")
- **Related documents** (the agreement should reference these, not copy them):
  `docs/safety-and-compliance.md`, `docs/onboarding.md`, `docs/offboarding.md`,
  `docs/call-flow.md`, and the client's `clients/<name>/config.yaml`

---

## 1. Scope of service
- An automated assistant answers the client's calls **forwarded** to a CallCatch number during agreed times (after hours and/or after N rings).
- It collects: the problem, callback number, name, service address, urgency, and best callback time.
- It sends the client a summary by text and/or email, per `notifications.channel`.
- It detects emergencies and pages the on-call number (`emergencies.on_call_number`, then `backup_on_call_number`), using the fixed Tier 1 list plus any client-approved `extra_emergency_triggers`.
- Optional: checks or books calendar slots, only if `booking.enabled` is true.
- **Out of scope:** outbound calls or texts to the client's customers; taking payments; quoting prices beyond `pricing.approved_wording`; diagnosis or advice; live call transfer (TODO(me): unless added later).
- The service uses third-party vendors (voice platform, AI model provider, messaging), listed in an exhibit. TODO(me): a vendor list exhibit.

## 2. What we do not promise
- **No guaranteed lead volume, bookings, or revenue.**
- **No guarantee of call quality,** transcription accuracy, or that every detail will be captured correctly. Summaries may contain errors, and the client should confirm details on callback.
- **No guaranteed uptime.** Vendor outages can happen. If the AI fails, the fallback is plain voicemail (`docs/call-flow.md` section 6). TODO(me): whether to offer a service-level target, and any credits.
- **Not an emergency service, and not a substitute for 911.** The assistant tells callers in danger to call 911 and pages the client. It **can't guarantee** that a page is delivered, that anyone responds, or that the caller acts on instructions.
- **No promise of response or arrival times** to callers. Callbacks are the client's responsibility.
- The assistant always discloses that it is automated. The client **can't** ask us to make it pose as a person.

## 3. Client responsibilities
- **Callback speed:** return calls within the client's stated `notifications.callback_promise`. That promise is the client's commitment, not ours.
- **Accurate business information:** business hours, services offered and not offered, service area, and pricing wording. Tell us promptly about changes; we update the config under its changelog.
- **Emergency rules:** review and approve the extra emergency triggers and the on-call and backup numbers. Acknowledge that the Tier 1 list and 911 instructions are fixed and can't be changed or removed.
- **Keep forwarding working** on their phone line, and tell us before changing carriers or numbers.
- **Their own legal obligations** in their trade and state (licensing, their own recordkeeping). VERIFY / ATTORNEY: whether any of the client's own obligations interact with call recording or consumer contact.
- **Tell us promptly** about wrong summaries, missed pages, or complaints from callers.

### 3a. Warranty of authority for approvals and on-call numbers
The client warrants that:
- The approval recorded in **`emergencies.owner_approval`** (`approved_by`, `approved_on`), covering the on-call and backup numbers and any extra emergency triggers, was given by a person with **actual authority** to approve it on the business's behalf.
- The opt-in recorded in **`notifications.owner_opt_in`** (`approved_by`, `approved_on`), covering emergency pages and summaries sent to the listed numbers and emails, was given by a person with **actual authority** to give it on the business's behalf.
- **`emergencies.on_call_number`**, **`emergencies.backup_on_call_number`**, and the numbers in **`notifications.sms_to`** are numbers the business **wants paged at any hour** for emergencies, and has the right to have paged.
- The client will tell us promptly when any of these people or numbers change, and will re-approve.
- ATTORNEY: consequences if the warranty is false (e.g. a number belongs to a former employee).

### 3b. Onboarding as a condition of go-live
- Go-live happens only after the onboarding checklist (**`docs/onboarding.md`**) is complete. This is a **condition precedent**: something that must happen before our obligation to go live begins.
- In particular: the written approvals (onboarding step 3), clean config validation (step 6), the live emergency page test to the real on-call and backup numbers (step 7.4), and the owner walkthrough, including hearing a Tier 1 test call (step 8).
- The client agrees to take part in the steps marked "with the owner".
- ATTORNEY: how to attach or incorporate the checklist, and what happens if the client insists on going live without completing it (the default should be: we don't go live).

## 4. Pilot terms
- Length: TODO(me) (e.g. 30 or 60 days).
- Pilot fee: TODO(me), or discounted or free setup.
- Success measures shared with the client: calls handled, emergencies paged, and the owner's own callback results.
- At the end: convert to standard terms, or end with offboarding per `docs/offboarding.md`.
- Everything else (data, disclosure, emergency limits, liability) applies during the pilot too.

## 5. Fees and retainer
- **One-time setup fee:** TODO(me). Covers onboarding, config, and number provisioning.
- **Monthly retainer:** TODO(me). Includes a call or minute allowance (section 6).
- Billing timing, payment method, late fees, taxes: TODO(me).
- Price changes: TODO(me) notice period.
- Pricing is informed by `docs/unit-economics.md`. VERIFY that vendor costs are current before quoting.

## 6. Usage caps and overage
- The retainer includes TODO(me) calls or minutes per month.
- Overage: TODO(me), a per-call or per-minute rate, or a hard cap.
- **What happens at the cap:** TODO(me) + ATTORNEY. Options: keep answering and bill overage; switch to voicemail only; notify the client at 80% and 100%.
  **Open question:** should emergency detection and paging keep working after a cap is reached, even if normal calls drop to voicemail? Stopping it could create safety and liability exposure.
- Our internal spend caps (`.env`) exist to protect against runaway costs. The agreement should explain what the client experiences if one triggers.

## 7. Data handling and retention
- **Governing rules:** `docs/safety-and-compliance.md` sections 5–8. The agreement should reference them, not restate them.
- We collect only the listed call fields. We never ask for payment, ID, or health details (safety doc section 5).
- **Retention:** per the client's `data.retention_days`. The shorter of that and the agreement wins. Then automatic deletion.
- **Separation:** one number, one config, and separate storage per client (safety doc section 7).
- **Vendors:** we use vendors that don't train on call data where available. VERIFY each vendor. List them in an exhibit.
- **Security incidents:** we notify the client within TODO(me) of discovering an incident affecting their data. ATTORNEY: our breach-notification duties versus the client's.
- **Client access and export:** what the client can request during the term and at offboarding. TODO(me).
- ATTORNEY: US terminology for our role (a service provider processing data for the client) and any state privacy-law contract terms required.

## 8. Call recording and disclosure responsibilities
- The greeting always (a) discloses the automated assistant and (b) gives a recording notice that **matches what we store**. This is enforced by the config validator, which rejects mismatches in both directions.
- Storage settings (`recording.stores_audio`, `recording.stores_transcripts`) are chosen at onboarding, before the greeting is finalized.
- The client can't ask us to remove or weaken the disclosure or the recording notice.
- **Who is responsible for what:** TODO(me) + ATTORNEY. For example: we provide a compliant greeting and settings; the client is responsible for its own separate recording of calls, if any.
- Variant C (no recording notice) only with attorney sign-off and nothing stored.
- ATTORNEY: see the questions in `docs/safety-and-compliance.md` section 14 (all-party consent, transcripts as recordings, vendor eavesdropping theories).

## 9. Phone number ownership
- The agent number is provisioned **under our company account** (onboarding step 7.1). The client doesn't own it unless agreed.
- At termination, per offboarding step 2: **release** it, **keep** it in our account, or **port** it to the client. TODO(me): the default, and any porting fee.
- A kept number isn't reassigned to another business until a **cooling-off period** has passed (TODO(me): length), so old callers don't reach a new business.
- The client's own business number always stays the client's. We only receive calls forwarded from it.
- VERIFY: the telephony provider's rules on porting and number ownership.

## 10. Limitation of liability
- Standard items for the attorney to draft: a liability cap (e.g. fees paid in the prior N months, TODO(me)), exclusion of indirect or consequential damages, and carve-outs. **ATTORNEY.**
- Tie back to section 2 (what we don't promise).

### 10a. Emergency paging — SEPARATE OPEN QUESTION FOR THE ATTORNEY
> **TODO(me) — ATTORNEY. Not drafted on purpose. Don't fold this into the general cap without discussing it.**
>
> Emergency detection and paging is the one function where a delay or failure has
> the highest real-world stakes: a gas leak, carbon monoxide, fire, or flooding
> near electrics. Questions to settle with the attorney:
> 1. **Whether** liability for the emergency-paging function should be limited
>    differently from the rest of the service, and **whether** such a limit would
>    even be enforceable in the governing state (some states restrict limiting
>    liability for gross negligence or personal injury). VERIFY.
> 2. **How** it interacts with the "not an emergency service / not a 911
>    substitute" statements in section 2, and where those must also appear (the
>    greeting? onboarding? the agreement's first page?).
> 3. What happens if paging fails for reasons outside our control: vendor or
>    carrier outages, an unreachable or out-of-date on-call number, or a client
>    who doesn't answer.
> 4. How the client's warranty in section 3a (authority, correct on-call
>    numbers) and the condition precedent in section 3b (the live page test)
>    affect the allocation of risk.
> 5. Whether errors-and-omissions or other insurance (section 13) should be
>    sized around this function specifically.
>
> This question is also item 1 in section 15.

## 11. Indemnification
- **Client indemnifies us** for: inaccurate business information they supplied; a false authority warranty (section 3a); their own legal violations; their handling of callbacks. ATTORNEY.
- **We indemnify the client** for: TODO(me) + ATTORNEY (e.g. our own violations of law, or data breaches caused by our negligence).
- Procedures (notice, control of defense): ATTORNEY.

## 12. Term, cancellation, and offboarding
- Initial term: TODO(me). Renewal: TODO(me) (auto-renew or month-to-month).
- Cancellation by either side: TODO(me) days' notice. Immediate termination for material breach: ATTORNEY.
- **Offboarding follows `docs/offboarding.md`**, including:
  - stopping forwarding before anything else
  - number disposition per section 9, including the **cooling-off period** before reuse
  - export (if agreed), then deletion of call data, including vendor-side where possible
  - **permanent deletion of the client's private contact file** (`clients/<name>/private/`) from every machine and secret store
  - written confirmation to the client
- Fees owed at termination, and any refunds: TODO(me).

## 13. Insurance
- Discuss with a licensed **insurance professional**, not decided here:
  - **Errors and omissions (E&O)** / professional liability: covers claims that our service failed to do what it should, which is especially relevant to emergency paging (section 10a).
  - **Cyber liability:** data breaches and incident response.
  - **General liability.**
- Whether to require the client to carry any insurance: TODO(me).
- VERIFY: coverage types, limits, and cost with an insurance professional.

## 14. Governing law and disputes
- Governing law: **TODO(me)**. State to be decided with the attorney.
- Venue and dispute resolution (court, arbitration, informal negotiation first): ATTORNEY.
- Other standard sections the attorney may add: confidentiality, notices, assignment, force majeure, entire agreement, amendments (including how config changes are approved), and survival of terms.

## 15. Questions for the attorney (in priority order)
1. **Emergency paging liability** (section 10a). Can and should liability for this function be treated differently, and how does that interact with the "not a 911 substitute" statements?
2. What happens at usage caps (section 6): must emergency handling continue?
3. How to make the onboarding checklist a condition precedent (section 3b), and the consequences of a false authority warranty (section 3a).
4. Recording and disclosure responsibilities between us and the client (section 8), plus the questions in safety doc section 14.
5. Our role and required privacy terms for handling call data (section 7), and breach-notification duties.
6. Liability cap and indemnities (sections 10–11).
7. Number ownership and porting terms (section 9).
8. Governing law and dispute resolution (section 14).
