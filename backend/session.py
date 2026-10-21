"""
Per-call conversation state and the agentic turn loop.

One CallSession is created when a call arrives and lives until the call ends
(status callback) or the server restarts. Sessions are keyed by Twilio's
CallSid, which is unique per call.

The turn loop:
  1. Append the caller's speech as a user message.
  2. Ask the LLM for a reply.
  3. If the reply contains tool calls, execute them and loop.
  4. Return the final assistant text and a flag indicating whether to hang up.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.adapters.llm_base import LLMAdapter, LLMTurn, ToolResult
from backend.tool_executors import run_tool


_MAX_TURNS = int(os.environ.get("MAX_LLM_TURNS_PER_CALL", "30"))
_HANGUP_AFTER_SAVE = os.environ.get("HANGUP_AFTER_SAVE", "1").strip() == "1"


@dataclass
class CallSession:
    call_sid: str
    client_id: str
    config: dict
    system_prompt: str
    adapter: LLMAdapter
    conversation: list = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    turn_count: int = 0
    save_called: bool = False

    def process_turn(self, speech: str) -> tuple[str, bool]:
        """
        Run one voice turn.

        Args:
            speech: The caller's transcribed words (may be empty string if silent).

        Returns:
            (text_to_speak, should_hangup)
        """
        if not speech.strip():
            speech = "(caller said nothing)"

        self.conversation.append({"role": "user", "content": speech})
        self.turn_count += 1

        if self.turn_count > _MAX_TURNS:
            return (
                "I'm sorry, we've been talking for a while and I need to close out. "
                "I'll make sure your message is saved. Goodbye.",
                True,
            )

        from backend.tools import TOOLS as TOOL_DEFS
        text, should_hangup = self._agentic_loop(TOOL_DEFS)
        return text, should_hangup

    def _agentic_loop(self, tool_defs: list) -> tuple[str, bool]:
        """Drive the LLM until it stops issuing tool calls. Return (text, hangup)."""
        should_hangup = False

        for _ in range(10):  # safety cap on tool-call rounds per turn
            turn: LLMTurn = self.adapter.respond(
                system_prompt=self.system_prompt,
                conversation=self.conversation,
                tools=tool_defs,
            )

            # Collect any text from this turn
            reply_text = turn.text or ""

            if not turn.tool_calls:
                # No tool calls — final text for this turn
                self.conversation.append({"role": "assistant", "content": reply_text})
                break

            # Append assistant turn with tool calls
            self.conversation.append({
                "role": "assistant",
                "content": reply_text,
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in turn.tool_calls
                ],
            })

            # Execute each tool call
            tool_results = []
            for tc in turn.tool_calls:
                result = run_tool(tc.name, tc.arguments, self.config, self.call_sid)
                tool_results.append(ToolResult(call_id=tc.id, content=result, is_error=False))

                if tc.name == "save_message":
                    self.save_called = True
                    if _HANGUP_AFTER_SAVE:
                        should_hangup = True

            # Append tool results
            self.conversation.append({
                "role": "tool",
                "tool_results": [
                    {"call_id": tr.call_id, "content": tr.content, "is_error": tr.is_error}
                    for tr in tool_results
                ],
            })

        else:
            reply_text = "I've taken note of your message. Goodbye."
            should_hangup = True

        return reply_text, should_hangup
