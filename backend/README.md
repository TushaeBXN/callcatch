# backend/

Application code. Right now it holds only what the test runner needs.

| File | What it does |
|---|---|
| `adapters/llm_base.py` | The `LLMAdapter` interface every LLM provider must implement. |
| `adapters/stub_adapter.py` | A fake LLM for testing the plumbing. No network, no cost. |
| `adapters/anthropic_adapter.py` | Talks to Claude using the official `anthropic` SDK. Reads `LLM_API_KEY` and `LLM_MODEL` from `.env`, and never prints them. |
| `adapters/__init__.py` | `get_llm_adapter()` picks an adapter based on `LLM_PROVIDER` in `.env`. |
| `tools.py` | The three tool definitions: `save_message`, `notify_owner`, `check_or_book_slot`. No others. |
| `prompt_builder.py` | Builds the system prompt (base prompt plus the model-facing part of the client config) and loads `.env`. Refuses an invalid config. |
| `config_schema.py` | The client config rules. Fails closed: unknown keys, safety changes, or disclosure mismatches are rejected. |

**Adding another LLM provider:** write a new class in `adapters/` that inherits
from `LLMAdapter`, then add it to `get_llm_adapter()`. No other code should
import a provider's library.

The voice-platform adapter and the real tool implementations come later (see
`docs/architecture.md`).
