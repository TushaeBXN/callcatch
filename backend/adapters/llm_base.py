"""
The LLM adapter interface.

An "adapter" is a thin wrapper that lets the rest of CallCatch talk to any
LLM provider the same way. To add a new provider, write a class that inherits
from LLMAdapter and implements respond(). Nothing else in the code should
import a provider's library directly.

Conversation format (provider-neutral), a list of dicts:
    {"role": "user", "text": "..."}                      # what the caller said
    {"role": "assistant", "text": "...",                 # what the assistant said
     "tool_calls": [ToolCall, ...], "raw": <anything>}   # raw = provider's own reply, reused as-is
    {"role": "tool", "results": [ToolResult, ...]}       # results of the tools it called
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ToolResult:
    call_id: str
    content: str
    is_error: bool = False


@dataclass
class LLMTurn:
    """One reply from the model."""
    text: str
    tool_calls: list = field(default_factory=list)
    stop_reason: str = ""
    raw: Any = None               # provider-specific reply, passed back unchanged next turn
    input_tokens: int = 0
    output_tokens: int = 0


class LLMAdapter(ABC):
    name = "base"

    @abstractmethod
    def respond(self, system_prompt: str, conversation: list, tools: list) -> LLMTurn:
        """Send the conversation so far and return the model's next turn."""
        raise NotImplementedError


class MissingSettingError(Exception):
    """Raised when a required .env setting is missing. Message names the setting, never its value."""
