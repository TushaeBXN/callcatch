# Client Onboarding Checklist

*An operational checklist, not a legal document.* Where a step touches something
another file governs, this checklist **points to that file** instead of
restating it, so each rule has one source of truth:

| Topic | Source of truth |
|---|---|
| Config fields, required approvals, disclosure/storage matching | `backend/config_schema.py` (run with `tests/validate_config.py`) and the comments in `clients/_template/config.yaml` |
| Real vs. tracked contact details | `clients/README.md` |
| Recording consent, retention, data handling | `docs/safety-and-compliance.md` |
| Forwarding types and carrier codes | `docs/call-flow.md` section 1 |
| Emergency tiers (fixed Tier 1, Tier 2 questions) | `docs/call-flow.md` section 4 and `prompts/base_system_prompt.md` section 6 |

**Hard rule:** no client goes live until **steps 1–8 are all checked**, in order.
Step 3 (written approvals) comes before step 6 (clean validation) on purpose:
the validator rejects a config without the approvals, so a clean result proves
the owner agreed. **Never type in an approval the owner didn't actually give.**

## Roles

| Role | Who | TODO(me) |
|---|---|---|
| **Account lead** | Runs the relationship with the owner, and collects approvals | Assign |
| **Folder owner** | The one person who edits `clients/<name>/` (see CONTRIBUTING.md) | Assign per client |
| **Tech** | Provisions numbers, forwarding, and monitoring | Assign |
| **Owner** | The client business owner | n/a |

Use `client-name` below as a stand-in for the real folder name, e.g. `acme-hvac`.

---

## Before go-live

### Step 1 — Discovery call
| # | Task | Who owns this step | Done |
|---|---|---|---|
| 1.1 | How many calls do you miss per week, and when (evenings, weekends, busy days)? | Account lead | [ ] |
| 1.2 | What's your average job value? (Used in `docs/unit-economics.md`.) | Account lead | [ ] |
| 1.3 | Who calls customers back today, and how fast? Who will call back CallCatch leads, and within what time? That becomes `notifications.callback_promise`. | Account lead | [ ] |
| 1.4 | Walk through the fixed Tier 1 list and the Tier 2 defaults (`docs/call-flow.md` section 4). Are there situations **specific to this business** that should also count as emergencies? Write them down as candidate `extra_emergency_triggers`, Tier 1 or 2 only. The owner can add triggers but can't remove or change Tier 1. | Account lead | [ ] |
| 1.5 | Who is on call for emergencies, and who is the backup (a different person or phone)? | Account lead | [ ] |
| 1.6 | Which carrier or phone system is the business line on? (Needed in step 7.) | Account lead | [ ] |
| 1.7 | Does the owner want Spanish support? It's a planned feature; see `docs/roadmap.md`. | Account lead | [ ] |

### Step 2 — Create the client folder and fill in the config
| # | Task | Who owns this step | Done |
|---|---|---|---|
| 2.1 | Run `cp -r clients/_template clients/client-name` on a new `client/client-name` branch. Set `client_id` and `folder_owner`. | Folder owner | [ ] |
| 2.2 | Fill in `clients/client-name/config.yaml` (**tracked in git**). Contact fields must be fake or `PRIVATE`, never real. The rules are in `clients/README.md`. | Folder owner | [ ] |
| 2.3 | Create `clients/client-name/private/contacts.yaml` (**gitignored**) with the real agent, on-call, backup, SMS, and email contacts. Only the five keys listed in `clients/README.md` are allowed. | Folder owner | [ ] |
| 2.4 | Run `git status` and confirm nothing under `private/` is listed. | Folder owner | [ ] |

### Step 3 — Get the two written approvals (BEFORE anything goes live)
These fields are **not optional**. `tests/validate_config.py` already rejects a
config where either is missing (`backend/config_schema.py`). Onboarding is where
they get **collected**, never invented.

| # | Task | Who owns this step | Done |
|---|---|---|---|
| 3.1 | **`emergencies.owner_approval`**: the owner reviews, in writing, the extra emergency triggers from 1.4 (each Tier 1 or 2), and the on-call and backup numbers. Record `approved_by` (the owner's name) and `approved_on` (the date). | Account lead | [ ] |
| 3.2 | **`notifications.owner_opt_in`**: the owner agrees, in writing, to receive emergency pages and call summaries at those numbers and emails, **at any hour**. Record `approved_by` and `approved_on`. | Account lead | [ ] |
| 3.3 | Save the written approvals (the email or signed form) where the agreement is stored, not in git. TODO(me): choose where signed approvals are kept. | Account lead | [ ] |

### Step 4 — Business facts and greeting variant (with the owner)
| # | Task | Who owns this step | Done |
|---|---|---|---|
| 4.1 | Confirm `business_hours` (24-hour, local time, `closed` for closed days) and `after_hours_definition`, including holidays. | Folder owner, with the owner | [ ] |
| 4.2 | Confirm `services_offered` and `services_not_offered`. The assistant never guesses beyond these lists. | Folder owner, with the owner | [ ] |
| 4.3 | Confirm `pricing.approved_wording`. The default is `null`, meaning no pricing at all. If the owner wants specific wording, record it exactly, plus `approved_by`. | Folder owner, with the owner | [ ] |
| 4.4 | Pick the greeting variant (`docs/call-flow.md` section 2). B is the default for HVAC, plumbing, electrical, and roofing. **Don't finalize the text until step 5 is done.** | Folder owner, with the owner | [ ] |

### Step 5 — Storage choice, THEN the final greeting text
The greeting's disclosure must match what is stored, **in both directions**. The
validator rejects any mismatch (`backend/config_schema.py`, recording rules), and
only the greeting text and storage flags reach the model (`model_view` in the
same file). So the storage choice comes first.

| # | Task | Who owns this step | Done |
|---|---|---|---|
| 5.1 | Set `recording.stores_audio` and `recording.stores_transcripts`, following our current policy in `docs/safety-and-compliance.md` section 3. | Folder owner | [ ] |
| 5.2 | Write `greeting.text` and `recording.notice_wording` to match: "recorded and transcribed", "transcribed", or no notice (Variant C, only with attorney sign-off and nothing stored). | Folder owner | [ ] |
| 5.3 | **Read the final greeting aloud to the owner** with a timer. The goal is about 10 seconds. The 911 sentence in Variant B is never cut. | Folder owner, with the owner | [ ] |
| 5.4 | Set `data.retention_days` per the agreement and `docs/safety-and-compliance.md` section 6. | Folder owner | [ ] |

### Step 6 — Validate clean
| # | Task | Who owns this step | Done |
|---|---|---|---|
| 6.1 | Run `python tests/validate_config.py --require-private clients/client-name/config.yaml`. It must print **"All configs valid."** Any `ERROR` line, including an unfinished `TODO(me)` or a missing approval, blocks go-live. | Folder owner | [ ] |
| 6.2 | Open a PR. The pre-commit hook and CI run the same validation. A reviewer approves. | Folder owner | [ ] |
| 6.3 | Run a scenario check against this client's config: `python tests/run_scenarios.py --config clients/client-name/config.yaml --only E01 F01 I05 P01`. Review the sheet. | Folder owner | [ ] |

### Step 7 — Number, forwarding, and staging test
| # | Task | Who owns this step | Done |
|---|---|---|---|
| 7.1 | Provision the agent number **under our company account**, never the owner's. Put the real number in `private/contacts.yaml`. Number ownership follows the agreement (`docs/service-agreement-outline.md`). | Tech | [ ] |
| 7.2 | Test the whole flow on the **staging** number first, with real calls from a phone that isn't the business line. | Tech | [ ] |
| 7.3 | On staging, test the **voicemail fallback**: make the AI unavailable, and confirm the caller hears the recorded message and can leave voicemail, and that the owner gets it. This can't be tested by the scenario runner. | Tech | [ ] |
| 7.4 | Set up forwarding on the owner's line to the agent number, using the carrier table in `docs/call-flow.md` section 1. Fill in the table's "Verified on" column. Record the method and **how to turn it off** in `phone.forwarding_setup_notes`. | Tech, with the owner | [ ] |
| 7.5 | Make a test call to the owner's business number during the forwarding window, and confirm it reaches CallCatch. | Tech | [ ] |

### Step 8 — Owner walkthrough
| # | Task | Who owns this step | Done |
|---|---|---|---|
| 8.1 | The owner listens to a live test call from start to finish: greeting, information collection, and closing. | Account lead, with the owner | [ ] |
| 8.2 | The owner hears **one Tier 1 emergency** test call (for example, "I smell gas"), so they know exactly what callers will be told, and confirm they received the emergency page. | Account lead, with the owner | [ ] |
| 8.3 | The owner receives and understands a normal text and email summary, including the "call back within…" line. | Account lead, with the owner | [ ] |
| 8.4 | The owner knows how to turn forwarding off, and who to contact if something seems wrong. | Account lead | [ ] |

---

## Go-live and after

### Step 9 — Go-live and week-one review
| # | Task | Who owns this step | Done |
|---|---|---|---|
| 9.1 | Confirm steps 1–8 are all checked. Merge the PR. Turn forwarding on for real. | Account lead | [ ] |
| 9.2 | Add a changelog entry in the client's config: "Went live." | Folder owner | [ ] |
| 9.3 | Day 1 to 7: check the call logs daily. Look for dropped calls, wrong details, missed emergencies, and owner complaints. See `docs/monitoring.md`. | Tech | [ ] |
| 9.4 | Week-one review with the owner: what worked, and what to change. Every failure becomes a new test scenario (`tests/scenarios.yaml`). | Account lead | [ ] |

### Step 10 — Weekly report
| # | Task | Who owns this step | Done |
|---|---|---|---|
| 10.1 | Set up the weekly report to the owner: calls handled, emergencies paged, and the average time to callback where the owner reports it. The content is defined in `docs/monitoring.md`. TODO(me): the report format and how it's delivered. | Tech | [ ] |
| 10.2 | Add the client to the weekly internal log review (`docs/monitoring.md`). | Tech | [ ] |
