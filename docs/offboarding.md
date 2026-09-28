# Client Offboarding Checklist

*An operational checklist, not a legal document.* The service agreement decides
what happens to the phone number and to the data. This checklist carries out
those decisions. Rules live in their source files:

| Topic | Source of truth |
|---|---|
| Number ownership, export rights, notice periods | `docs/service-agreement-outline.md` (draft for attorney review) and the signed agreement |
| Retention and deletion, including vendor-side logs | `docs/safety-and-compliance.md` section 6, and this client's `data.retention_days` |
| Access and secrets | `SECURITY.md` |
| Where the client's files live | `clients/README.md` |

Roles are the same as in `docs/onboarding.md`. Use `client-name` as a stand-in
for the real folder name. **Do the steps in order.** Forwarding stops first, so no
caller reaches a service that's shutting down.

| # | Task | Who owns this step | Done |
|---|---|---|---|
| **1** | **Stop forwarding** | | |
| 1.1 | Agree the end date and time with the owner, in writing. | Account lead | [ ] |
| 1.2 | The owner (or Tech, with the owner) turns off call forwarding, using `phone.forwarding_setup_notes`. | Tech, with the owner | [ ] |
| 1.3 | Test call to the business number: confirm it no longer reaches CallCatch. | Tech | [ ] |
| 1.4 | Turn off emergency paging and summaries for this client, so nothing more is sent to their numbers. | Tech | [ ] |
| **2** | **Phone number disposition** | | |
| 2.1 | Check the agreement: release the number, keep it in our account, or port it to the client. | Account lead | [ ] |
| 2.2 | Carry out that choice with the telephony provider. VERIFY: the provider's porting and release steps and fees. | Tech | [ ] |
| 2.3 | If the number is kept, make sure it no longer routes to this client's config. Never reuse it for another client until TODO(me): a cooling-off period, so old callers don't reach a new business. | Tech | [ ] |
| **3** | **Export, then delete data** | | |
| 3.1 | If the agreement gives the client an export: send summaries (and transcripts, if agreed) securely. TODO(me): export format and secure delivery method. | Tech | [ ] |
| 3.2 | Get the client's written confirmation that they received the export, or that they declined it. | Account lead | [ ] |
| 3.3 | Delete this client's summaries, transcripts, and audio from our storage. Don't wait for `data.retention_days` to run out unless the agreement says to. Follow `docs/safety-and-compliance.md` section 6. | Tech | [ ] |
| 3.4 | Request deletion of vendor-side data (voice platform, LLM provider, SMS/email sender) where the vendor allows it. Record what each vendor confirmed. | Tech | [ ] |
| 3.5 | Record what was deleted, when, and by whom. Keep no copies. | Tech | [ ] |
| **4** | **Revoke access** | | |
| 4.1 | Remove any access the client had (future dashboard logins, shared folders). | Tech | [ ] |
| 4.2 | Remove this client's per-client credentials or webhooks. If any secret was shared with the client, rotate it (`SECURITY.md`). | Tech | [ ] |
| 4.3 | Remove team members' access that existed only for this client. | Account lead | [ ] |
| **5** | **Archive the config, destroy the private files** | | |
| 5.1 | Add a final changelog entry to `clients/client-name/config.yaml`, e.g. "Offboarded on YYYY-MM-DD, number released, data deleted." | Folder owner | [ ] |
| 5.2 | In the same PR, move the tracked config to `clients/_archive/client-name/config.yaml`. It contains no real contact details, so it's safe to keep as an audit trail. Archived configs aren't validated or loaded. TODO(me): confirm archive vs. full removal. | Folder owner | [ ] |
| 5.3 | **Permanently delete `clients/client-name/private/`** from every machine and secret store that has a copy. Never move it into `_archive/`. Git never tracked it, so there's nothing to clean up in git. | Folder owner | [ ] |
| 5.4 | Run `python tests/validate_config.py` and confirm it no longer lists this client. | Folder owner | [ ] |
| **6** | **Final report and confirmation** | | |
| 6.1 | Send the client a final report: the service period, calls handled, and emergencies paged. | Account lead | [ ] |
| 6.2 | Send written confirmation that forwarding has stopped, the number has been handled as agreed, data has been exported (if agreed) and deleted, and access has been revoked. | Account lead | [ ] |
| 6.3 | Remove the client from weekly reports and the log review (`docs/monitoring.md`). | Tech | [ ] |
