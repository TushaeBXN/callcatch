# tests/

| File | What it does |
|---|---|
| `scenarios.yaml` | The test calls, readable by the software. **Edit this one.** |
| `scenarios.md` | The same scenarios as a human checklist. Generated, so don't edit it by hand. |
| `make_checklist.py` | Regenerates `scenarios.md` from the YAML. |
| `run_scenarios.py` | Plays each call against the model and writes a review sheet to `tests/reports/` (gitignored). |
| `check_prompt_sync.py` | Fails if the Tier 1 and Tier 2 safety wording in the prompt and in `docs/call-flow.md` stop matching. |
| `validate_config.py` | Validates every client config against `backend/config_schema.py`. Exit 1 on any error. |
| `test_validate_config.py` | Proof tests: every rejection rule triggers, and a clean config passes. `python -m unittest tests/test_validate_config.py -v` |

## Typical workflow

```bash
python tests/check_prompt_sync.py
```
Checks that the safety wording matches. Free, and needs no installs.

```bash
python tests/run_scenarios.py --dry-run
```
Builds a review sheet without calling any model. Free. Use this to check the plumbing.

```bash
python tests/run_scenarios.py --only E01 F01 I01
```
A live run on three scenarios. Needs `LLM_PROVIDER=anthropic`, a key, and a model in `.env`. Costs a little.

Then open the newest `tests/reports/<date-time>/review.md`, read each
transcript, and fill in PASS or FAIL.

**Before live runs:** set a monthly spend limit in the provider's console. Start
with a few scenarios, not all of them. The runner asks for confirmation before
more than 5 live scenarios.

**The runner doesn't grade.** A person decides pass or fail. Any "must NOT do"
that happened is a FAIL.

**The voicemail fallback** (the AI is down, so the caller hears a recording and
leaves voicemail) lives in the voice platform. It needs a manual test on the
staging number and can't be tested here.
