"""
Anthropic adapter: sends the conversation to Claude via the official
Anthropic Python SDK (install with: pip install anthropic).

Settings come from .env, never from code:
    LLM_API_KEY  - your Anthropic API key (never printed or logged)
    LLM_MODEL    - the model name. VERIFY current names at docs.anthropic.com.

The SDK is imported inside __init__, so people using the stub or --dry-run
don't need it installed.
"""

import os

from .llm_base import LLMAdapter, LLMTurn, MissingSettingError, ToolCall

# One spoken turn is short, but leave headroom so replies are never cut off.
MAX_TOKENS = 16000


class AnthropicAdapter(LLMAdapter):
    name = "anthropic"

    def __init__(self):
        api_key = os.environ.get("LLM_API_KEY", "")
        model = os.environ.get("LLM_MODEL", "")
        if not api_key or api_key.startswith("fake-"):
            raise MissingSettingError("LLM_API_KEY is not set in .env (the example value doesn't count).")
        if not model or model.startswith("replace-with"):
            raise MissingSettingError("LLM_MODEL is not set in .env.")

        try:
            import anthropic
        except ImportError:
            raise MissingSettingError(
                "The 'anthropic' package isn't installed. Inside your virtual environment run: pip install anthropic"
            )

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def respond(self, system_prompt, conversation, tools):
        response = self._client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=tools,
            messages=self._to_anthropic_messages(conversation),
        )

        text_parts, tool_calls = [], []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))

        stop_reason = response.stop_reason or ""
        if stop_reason == "refusal" and getattr(response, "stop_details", None):
            stop_reason = f"refusal ({response.stop_details.category})"

        return LLMTurn(
            text=" ".join(text_parts).strip(),
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            raw=response.content,          # passed back unchanged on the next turn
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    @staticmethod
    def _to_anthropic_messages(conversation):
        """Convert the neutral conversation into Anthropic's message format."""
        messages = []
        for item in conversation:
            if item["role"] == "user":
                content = [{"type": "text", "text": item["text"] or "[caller is silent]"}]
                role = "user"
            elif item["role"] == "assistant":
                content = item["raw"]
                role = "assistant"
            else:  # tool results go back to the model as a user message
                content = [
                    {"type": "tool_result", "tool_use_id": r.call_id, "content": r.content, "is_error": r.is_error}
                    for r in item["results"]
                ]
                role = "user"

            # The API expects user/assistant to alternate, so merge back-to-back user messages.
            if messages and messages[-1]["role"] == role == "user":
                messages[-1]["content"] = list(messages[-1]["content"]) + content
            else:
                messages.append({"role": role, "content": content})
        return messages
