"""
The assistant's three tools, and NO others.

These are the tool *definitions* the model sees: a name, a description, and
the allowed inputs, written as JSON Schema (a standard way to describe data).
The real implementations come later. The test runner simulates them.

Safety notes (see docs/safety-and-compliance.md, section 9):
- notify_owner has NO destination field. The backend sends only to the numbers in the client config.
- Everything the model puts in these fields came from a caller. Treat it as untrusted text.
"""

URGENCY = ["tier1_emergency", "tier2_urgent", "routine", "unknown"]
FLAGS = [
    "upset_caller", "poor_audio", "outside_service_area", "vulnerable_occupant",
    "home_not_secure", "likely_spam_or_sales", "wrong_number", "non_english", "caller_hung_up",
]

TOOLS = [
    {
        "name": "save_message",
        "description": "Save the caller's details and a short summary for this business. Call once before the call ends.",
        "input_schema": {
            "type": "object",
            "properties": {
                "problem": {"type": "string", "description": "What's wrong, in the caller's own words."},
                "callback_number": {"type": "string", "description": "Callback number the caller confirmed."},
                "name": {"type": "string"},
                "service_address": {"type": "string"},
                "urgency": {"type": "string", "enum": URGENCY},
                "best_callback_time": {"type": "string"},
                "flags": {"type": "array", "items": {"type": "string", "enum": FLAGS}},
                "notes": {"type": "string", "description": "Short extra notes. Quote caller text as: Caller said: \"...\""},
            },
            "required": ["problem", "urgency"],
            "additionalProperties": False,
        },
    },
    {
        "name": "notify_owner",
        "description": (
            "Send a summary to the business's configured on-call contact. "
            "Use priority 'emergency' for Tier 1 and Tier 2, otherwise 'normal'. "
            "You cannot choose the recipient. Returns status 'delivered' (success), 'pending' (not yet confirmed), or 'failed'. Only 'delivered' counts as success."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string", "enum": ["emergency", "normal"]},
                "summary": {"type": "string", "description": "Short summary. Caller's words must be quoted."},
            },
            "required": ["priority", "summary"],
            "additionalProperties": False,
        },
    },
    {
        "name": "check_or_book_slot",
        "description": (
            "Check or book a callback/appointment slot on this business's calendar. "
            "Only if the client config enables booking and the caller asks. "
            "Read the slot back and get a clear yes before booking."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["check", "book"]},
                "requested_time": {"type": "string", "description": "What the caller asked for, e.g. 'tomorrow morning'."},
                "slot_id": {"type": "string", "description": "Slot to book, from a previous 'check' result."},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
]

TOOL_NAMES = [t["name"] for t in TOOLS]
assert TOOL_NAMES == ["save_message", "notify_owner", "check_or_book_slot"], "Exactly three tools. No more."
