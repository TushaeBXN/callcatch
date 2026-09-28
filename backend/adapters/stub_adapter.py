"""
Stub adapter: a fake LLM for testing the plumbing. No network, no cost.

It does NOT behave like a real receptionist. It exists so beginners can run the
whole pipeline (prompt building, tool simulation, report writing) for free.
If the caller mentions an obvious emergency word, it calls notify_owner, so the
tool-simulation path gets exercised too.
"""

from .llm_base import LLMAdapter, LLMTurn, ToolCall

EMERGENCY_WORDS = ("gas", "smoke", "fire", "carbon", "sparking", "burning")


class StubAdapter(LLMAdapter):
    name = "stub"

    def __init__(self):
        self._counter = 0

    def respond(self, system_prompt, conversation, tools):
        last = conversation[-1]
        if last["role"] == "tool":
            return LLMTurn(text="[stub] I'll get this to the team right away.", stop_reason="end_turn")

        said = last.get("text", "").lower()
        if any(word in said for word in EMERGENCY_WORDS):
            self._counter += 1
            call = ToolCall(
                id=f"stub_call_{self._counter}",
                name="notify_owner",
                arguments={"priority": "emergency", "summary": "[stub] possible emergency"},
            )
            return LLMTurn(text="", tool_calls=[call], stop_reason="tool_use")

        return LLMTurn(text="[stub] Got it. What's the best number to reach you?", stop_reason="end_turn")
