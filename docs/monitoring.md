# Monitoring

What we watch, what wakes someone up, and the weekly routine that turns every
failure into a test. Thresholds are TODO(me) until real traffic gives us a
baseline.

## Alerts

### 1. The emergency path (highest priority)
Emergency paging is the function where a failure matters most
(`docs/service-agreement-outline.md` section 10a). These alerts go to the
operator **immediately, at any hour**.

| Alert | Trigger | Why |
|---|---|---|
| `notify_owner` failed (emergency priority) | Any single failure | The owner may not know about a gas leak or flood |
| Delivery not confirmed | Emergency page still `pending` after TODO(me) seconds | "Sent" isn't "delivered". The assistant only says "alerted" on confirmed delivery. |
| Retries used | An emergency page needed a retry | An early warning, before outright failure |
| **Backup number escalation** | The primary on-call page failed, so the backup was paged | Owner contact details may be stale. Follow up with the client the same day. |
| Final text fallback used | Both pages failed, so a text went out | Treat as an incident |
| Tier 1 without a page | A call was classified Tier 1 but no `notify_owner` was attempted | A model or prompt failure. Add a scenario right away. |

### 2. Call handling
| Alert | Trigger |
|---|---|
| Failed calls | Calls that errored or ended with no `save_message`: over TODO(me)% in an hour |
| Voicemail fallback triggered | The AI was unavailable and callers went to voicemail: any occurrence |
| Hang-up spike | Calls under TODO(me) seconds rise above TODO(me)× the 7-day baseline (the greeting, audio, or latency may be broken) |
| Silent or no-audio calls | A spike in calls with no caller speech (a forwarding or audio problem) |
| Slow replies | Median time before the assistant starts speaking over TODO(me) seconds |
| Model refusals or cut-offs | Any `refusal` or `max_tokens` stop reason in production |

### 3. Vendors
| Alert | Trigger |
|---|---|
| Vendor outage | The voice, LLM, SMS, or email provider's status page shows an incident, or our error rate for that vendor jumps |
| Webhook signature failures | Any occurrence (misconfiguration, or someone probing the endpoint) |

### 4. Cost
| Alert | Trigger |
|---|---|
| Spend caps | 50%, 80%, and 100% of `SPEND_CAP_DAILY_USD` / `SPEND_CAP_MONTHLY_USD` (`.env`) and of each vendor console limit |
| Cost spike | Daily spend over TODO(me)× the 7-day average |
| Client past the usage-cap point | Monthly calls for a client pass the cap point from `docs/unit_economics.py`. That's a pricing conversation. What happens to emergency handling at a cap is still open (`docs/service-agreement-outline.md` section 6). |

### 5. Configuration and security
| Alert | Trigger |
|---|---|
| Config validation failure at deploy | `validate_config.py --require-private` fails, so the deploy is blocked |
| Secret-scan hit | GitHub secret scanning or gitleaks flags something. Follow `SECURITY.md`. |

**Logs are data too.** Keep raw transcripts and caller phone numbers **out of**
general logs, and use call IDs instead. Log retention follows the same limits
as call data (`docs/safety-and-compliance.md` section 6).

## Weekly log review (every week, about 30 minutes)

| # | Step | Who |
|---|---|---|
| 1 | Review every alert from the week, especially section 1, the emergency path | Tech |
| 2 | Sample TODO(me) calls per client: read the summary against the transcript. Were the details right? Was the tier right? | Tech |
| 3 | For **every** failure found, write a new scenario with **fake details** that reproduces it. Put it in `tests/scenarios.yaml` if it's general, or in `clients/<name>/scenarios.yaml` if it's specific to that client's extra triggers (onboarding step 6.4). Never paste real transcripts. | Tech |
| 4 | Run the new scenarios (and the affected category) with `tests/run_scenarios.py`, and review the sheet | Tech |
| 5 | If the fix is a prompt change: open a `prompt/` PR, bump the version in `prompts/CHANGELOG.md`, and link the new scenario | Prompt owner |
| 6 | If the fix is a config change: open a `client/` PR, add a changelog entry, and get the folder owner's approval | Folder owner |
| 7 | Any backup-number escalations: confirm the client's on-call details this week and re-approve (`emergencies.owner_approval`) | Account lead |
| 8 | Note costs against the cap point for each client | Founder |

## Weekly owner report (referenced by onboarding step 10.1)

Contents: calls handled, emergencies paged (and confirmed delivered), messages
flagged (spam, wrong number, upset caller), and any issues and fixes. TODO(me):
the format and how it's delivered. Keep caller details to the minimum. The owner
already receives each summary.
