"""Pick an LLM adapter based on the LLM_PROVIDER setting in .env."""

import os

from .llm_base import LLMAdapter, LLMTurn, MissingSettingError, ToolCall, ToolResult

PROVIDERS = ("stub", "anthropic")


def get_llm_adapter() -> LLMAdapter:
    provider = os.environ.get("LLM_PROVIDER", "stub").strip().lower()
    if provider == "stub":
        from .stub_adapter import StubAdapter
        return StubAdapter()
    if provider == "anthropic":
        from .anthropic_adapter import AnthropicAdapter
        return AnthropicAdapter()
    raise MissingSettingError(f"LLM_PROVIDER must be one of {PROVIDERS}, got '{provider}'.")


__all__ = ["get_llm_adapter", "LLMAdapter", "LLMTurn", "ToolCall", "ToolResult", "MissingSettingError"]
