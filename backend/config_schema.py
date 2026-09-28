"""
Client config validation. FAIL CLOSED: anything not explicitly allowed is rejected.

Used by:
  - tests/validate_config.py   (the pre-commit hook and CI)
  - backend/prompt_builder.py  (refuses to build a prompt from an invalid config)
  - tests/run_scenarios.py     (through prompt_builder)
  - the future deploy step     (with require_private=True)

What it enforces:
  1. Only known keys, at every level. Unknown or duplicate keys are rejected.
  2. Correct types and formats for every field. Every key is required, so
     each choice is explicit (use null for "none").
  3. Clients can't touch Tier 1, 911, or safety rules. The only safety-related
     things a client may set are extra emergency triggers (Tier 1 or 2, never
     lower) and on-call numbers.
  4. The greeting discloses the automated assistant.
  5. The recording notice matches what's stored, in BOTH directions: never
     less than we store, never more.
  6. Variant C (no notice) only if nothing is stored, and only with attorney sign-off.
  7. No text anywhere that tries to undermine 911 or safety instructions.
  8. No real phone numbers or emails in git. Tracked configs use fake 555-01xx
     numbers and example.com emails, or the word PRIVATE, meaning the real value
     is in clients/<name>/private/contacts.yaml (gitignored).
"""

import copy
import datetime
import re
from pathlib import Path

import yaml

SCHEMA_VERSION = 1
MAX_RETENTION_DAYS = 365   # TODO(me): set our maximum retention after attorney review
TEMPLATE_ID = "_template"
PRIVATE = "PRIVATE"

TRADES = ["hvac", "plumbing", "roofing", "garage_doors", "auto_repair", "gutter_cleaning", "electrical"]
VARIANT_B_DEFAULT_TRADES = {"hvac", "plumbing", "electrical", "roofing"}
LANGUAGES = ["en", "es"]
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
MAX_GREETING_WORDS = 35    # about 10 seconds spoken

FAKE_PHONE = re.compile(r"^\+1-555-01\d\d$")
REAL_PHONE = re.compile(r"^\+1-?\d{3}-?\d{3}-?\d{4}$")
FAKE_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@example\.com$")
REAL_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
HOURS = re.compile(r"^(([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d|closed)$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DISCLOSURE = re.compile(r"\bautomated\b[^.?!]{0,40}\bassistant\b", re.I)

# Key names that signal an attempt to change safety rules or instructions.
FORBIDDEN_KEY = re.compile(r"tier_?1|911|safety|override|disable|system_prompt|instruction|rule", re.I)

# Text that tries to undermine safety, anywhere in the config.
UNDERMINING = [
    (re.compile(r"\b(don'?t|do not|never|no need to|shouldn'?t)\b[^.]{0,40}\b(call|dial)\w*\s*911", re.I), "tells people not to call 911"),
    (re.compile(r"\bnot (an? |considered an? )?emergenc", re.I), "declares something 'not an emergency'"),
    (re.compile(r"\bignore\b[^.]{0,30}\b(rules?|instructions?|prompt|tier)", re.I), "tells the assistant to ignore its rules"),
    (re.compile(r"\b(skip|remove|disable|omit)\b[^.]{0,30}\b(911|tier ?1|safety|disclos\w*|recording notice)", re.I), "tries to remove safety or disclosure steps"),
    (re.compile(r"\byou are (now )?(a |the )?(human|person|owner)\b", re.I), "tells the assistant to claim it's a person or the owner"),
]


# ---------- schema definition ----------

def f(kind, *, required=True, nullable=False, **extra):
    """Describe one field. Every field is required unless stated."""
    return {"kind": kind, "required": required, "nullable": nullable, **extra}


def approval():
    return f("dict", fields={"approved_by": f("str", nullable=True), "approved_on": f("date", nullable=True)})


SCHEMA = f("dict", fields={
    "schema_version": f("int"),
    "client_id": f("str"),
    "folder_owner": f("str"),
    "business": f("dict", fields={
        "name": f("str"),
        "trade": f("enum", values=TRADES),
        "timezone": f("str"),
        "service_area": f("list", item=f("str")),
        "business_hours": f("dict", fields={d: f("hours") for d in DAYS}),
        "after_hours_definition": f("str"),
        "services_offered": f("list", item=f("str")),
        "services_not_offered": f("list", item=f("str")),
    }),
    "phone": f("dict", fields={
        "agent_number": f("phone"),
        "carrier": f("str"),
        "forwarding_setup_notes": f("str"),
    }),
    "greeting": f("dict", fields={
        "variant": f("enum", values=["A", "B", "C"]),
        "text": f("str"),
        "variant_c_attorney_approved": f("bool"),
    }),
    "recording": f("dict", fields={
        "stores_audio": f("bool"),
        "stores_transcripts": f("bool"),
        "notice_wording": f("str", nullable=True),
    }),
    "languages": f("dict", fields={
        "supported": f("list", item=f("enum", values=LANGUAGES)),
        "other_language_line": f("str", nullable=True),
    }),
    "emergencies": f("dict", fields={
        "on_call_number": f("phone"),
        "backup_on_call_number": f("phone"),
        "extra_emergency_triggers": f("list", item=f("dict", fields={
            "description": f("str"),
            "tier": f("enum", values=[1, 2]),      # never 3: additions can't downgrade anything
        })),
        "owner_approval": approval(),
    }),
    "notifications": f("dict", fields={
        "channel": f("enum", values=["sms", "email", "both"]),
        "sms_to": f("list", item=f("phone")),
        "email_to": f("list", item=f("email")),
        "callback_promise": f("str"),
        "owner_opt_in": approval(),
    }),
    "pricing": f("dict", fields={
        "approved_wording": f("str", nullable=True),
        "approved_by": f("str", nullable=True),
    }),
    "booking": f("dict", fields={
        "enabled": f("bool"),
        "notes": f("str", nullable=True),
    }),
    "data": f("dict", fields={
        "retention_days": f("int"),
    }),
    "changelog": f("list", item=f("dict", fields={
        "date": f("date"),
        "by": f("str"),
        "change": f("str"),
    })),
})

# The private contacts file may hold ONLY these real contact values.
PRIVATE_SCHEMA = f("dict", fields={
    "agent_number": f("real_phone", required=False),
    "on_call_number": f("real_phone", required=False),
    "backup_on_call_number": f("real_phone", required=False),
    "sms_to": f("list", item=f("real_phone"), required=False),
    "email_to": f("list", item=f("real_email"), required=False),
})
PRIVATE_FIELDS = {  # tracked-config path -> private-file key
    ("phone", "agent_number"): "agent_number",
    ("emergencies", "on_call_number"): "on_call_number",
    ("emergencies", "backup_on_call_number"): "backup_on_call_number",
    ("notifications", "sms_to"): "sms_to",
    ("notifications", "email_to"): "email_to",
}


# ---------- YAML loading that rejects duplicate keys ----------

class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key '{key}' (line {key_node.start_mark.line + 1})", key_node.start_mark)
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def load_yaml(path):
    return yaml.load(Path(path).read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)


# ---------- type/shape checking ----------

class Result:
    def __init__(self):
        self.errors, self.warnings, self.todos = [], [], []

    @property
    def ok(self):
        return not self.errors


def _is_todo(v):
    return isinstance(v, str) and "TODO(me)" in v


def _check(value, spec, path, res):
    where = path or "(top level)"
    if value is None:
        if not spec["nullable"]:
            res.errors.append(f"{where}: must not be empty (null)")
        return
    if _is_todo(value) and spec["kind"] in ("str", "date", "phone", "email"):
        res.todos.append(f"{where}: {value}")
        return

    kind = spec["kind"]
    if kind == "dict":
        if not isinstance(value, dict):
            res.errors.append(f"{where}: must be a section of key: value pairs")
            return
        allowed = spec["fields"]
        for key in value:
            if key not in allowed:
                sub = f"{path}.{key}" if path else str(key)
                if FORBIDDEN_KEY.search(str(key)):
                    res.errors.append(f"{sub}: not allowed. Clients can't change Tier 1, 911, or safety rules, "
                                      f"or the assistant's instructions. Only extra_emergency_triggers and on-call numbers.")
                else:
                    res.errors.append(f"{sub}: unknown key (not in the schema). Unknown keys are rejected, not ignored.")
        for key, sub_spec in allowed.items():
            sub = f"{path}.{key}" if path else key
            if key not in value:
                if sub_spec["required"]:
                    res.errors.append(f"{sub}: missing (required; use null for 'none' where allowed)")
                continue
            _check(value[key], sub_spec, sub, res)
    elif kind == "list":
        if not isinstance(value, list):
            res.errors.append(f"{where}: must be a list")
            return
        for i, item in enumerate(value):
            _check(item, spec["item"], f"{path}[{i}]", res)
    elif kind == "str":
        if not isinstance(value, str) or not value.strip():
            res.errors.append(f"{where}: must be non-empty text")
    elif kind == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            res.errors.append(f"{where}: must be a whole number")
    elif kind == "bool":
        if not isinstance(value, bool):
            res.errors.append(f"{where}: must be true or false (got {value!r})")
    elif kind == "enum":
        if value not in spec["values"] or isinstance(value, bool):
            res.errors.append(f"{where}: must be one of {spec['values']} (got {value!r})")
    elif kind == "hours":
        if not isinstance(value, str) or not HOURS.match(value):
            res.errors.append(f"{where}: must be 'HH:MM-HH:MM' (24-hour) or 'closed' (got {value!r})")
    elif kind == "date":
        if isinstance(value, datetime.date):
            return
        if not isinstance(value, str) or not DATE.match(value):
            res.errors.append(f"{where}: must be a date like 2026-09-28")
    elif kind == "phone":
        if value == PRIVATE:
            return
        if not isinstance(value, str) or not FAKE_PHONE.match(value):
            res.errors.append(f"{where}: {value!r} isn't a fake +1-555-01xx number. Real numbers go in "
                              f"clients/<name>/private/contacts.yaml, with PRIVATE written here.")
    elif kind == "email":
        if value == PRIVATE:
            return
        if not isinstance(value, str) or not FAKE_EMAIL.match(value):
            res.errors.append(f"{where}: {value!r} isn't an @example.com address. Real emails go in "
                              f"clients/<name>/private/contacts.yaml, with PRIVATE written here.")
    elif kind == "real_phone":
        if not isinstance(value, str) or not REAL_PHONE.match(value):
            res.errors.append(f"{where}: must be a US number like +1-312-555-0142")
    elif kind == "real_email":
        if not isinstance(value, str) or not REAL_EMAIL.match(value):
            res.errors.append(f"{where}: must be an email address")


def _strings(value, path=""):
    """Yield (path, text) for every string in the config."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _strings(v, f"{path}[{i}]")
    elif isinstance(value, str):
        yield path, value


def _get(cfg, *keys):
    for k in keys:
        if not isinstance(cfg, dict):
            return None
        cfg = cfg.get(k)
    return cfg


# ---------- rules beyond shape ----------

def _check_rules(cfg, folder_name, res):
    if cfg.get("schema_version") != SCHEMA_VERSION:
        res.errors.append(f"schema_version: must be {SCHEMA_VERSION}")
    if folder_name is not None and cfg.get("client_id") != folder_name:
        res.errors.append(f"client_id: {cfg.get('client_id')!r} must match its folder name {folder_name!r}")

    # --- greeting: disclosure ---
    text = _get(cfg, "greeting", "text") or ""
    variant = _get(cfg, "greeting", "variant")
    if isinstance(text, str) and not DISCLOSURE.search(text):
        res.errors.append("greeting.text: must tell the caller they're talking to an automated assistant "
                          "(e.g. \"I'm an automated assistant\")")

    # --- recording notice must match storage, BOTH directions ---
    audio = _get(cfg, "recording", "stores_audio")
    transcripts = _get(cfg, "recording", "stores_transcripts")
    if isinstance(audio, bool) and isinstance(transcripts, bool) and isinstance(text, str):
        says_recorded = bool(re.search(r"\brecord", text, re.I))
        says_transcribed = bool(re.search(r"\btranscri", text, re.I))
        if audio and not says_recorded:
            res.errors.append("greeting.text: config stores AUDIO but the greeting doesn't say the call is recorded "
                              "(under-disclosure misleads callers)")
        if transcripts and not says_transcribed:
            res.errors.append("greeting.text: config stores TRANSCRIPTS but the greeting doesn't say the call is transcribed "
                              "(under-disclosure misleads callers)")
        if says_recorded and not audio:
            res.errors.append("greeting.text: greeting says the call is recorded but recording.stores_audio is false "
                              "(inaccurate disclosure: fix whichever is wrong)")
        if says_transcribed and not transcripts:
            res.errors.append("greeting.text: greeting says the call is transcribed but recording.stores_transcripts is false "
                              "(inaccurate disclosure: fix whichever is wrong)")

        notice = _get(cfg, "recording", "notice_wording")
        stores_anything = audio or transcripts
        if stores_anything and notice is None:
            res.errors.append("recording.notice_wording: required when audio or transcripts are stored")
        if not stores_anything and notice is not None:
            res.errors.append("recording.notice_wording: must be null when nothing is stored")
        if isinstance(notice, str) and not _is_todo(notice) and notice.lower() not in text.lower():
            res.errors.append(f"recording.notice_wording: {notice!r} must appear word for word in greeting.text")

        # --- Variant C ---
        if variant == "C" and stores_anything:
            res.errors.append("greeting.variant: C (no recording notice) is only allowed when NO audio and NO transcripts are stored")
        if variant == "C" and _get(cfg, "greeting", "variant_c_attorney_approved") is not True:
            res.errors.append("greeting.variant_c_attorney_approved: must be true (attorney sign-off) before using Variant C")

    if isinstance(text, str) and len(text.split()) > MAX_GREETING_WORDS:
        res.warnings.append(f"greeting.text: {len(text.split())} words. Aim for {MAX_GREETING_WORDS} or fewer (about 10 seconds).")
    if _get(cfg, "business", "trade") in VARIANT_B_DEFAULT_TRADES and variant != "B":
        res.warnings.append("greeting.variant: B (emergency first) is the default for HVAC, plumbing, electrical, and roofing")

    # --- emergencies: additions only (tier 1 or 2, checked by the schema), with written approval ---
    appr = _get(cfg, "emergencies", "owner_approval") or {}
    if isinstance(appr, dict) and (appr.get("approved_by") is None or appr.get("approved_on") is None):
        res.errors.append("emergencies.owner_approval: approved_by and approved_on are required "
                          "(owner approves on-call numbers and any extra triggers in writing)")
    on_call = _get(cfg, "emergencies", "on_call_number")
    if on_call is not None and on_call == _get(cfg, "emergencies", "backup_on_call_number") and on_call != PRIVATE:
        res.warnings.append("emergencies.backup_on_call_number: same as the on-call number, so there is no real backup")

    # --- notifications ---
    channel = _get(cfg, "notifications", "channel")
    if channel in ("sms", "both") and not _get(cfg, "notifications", "sms_to"):
        res.errors.append("notifications.sms_to: needs at least one number for channel " + repr(channel))
    if channel in ("email", "both") and not _get(cfg, "notifications", "email_to"):
        res.errors.append("notifications.email_to: needs at least one address for channel " + repr(channel))
    opt = _get(cfg, "notifications", "owner_opt_in") or {}
    if isinstance(opt, dict) and (opt.get("approved_by") is None or opt.get("approved_on") is None):
        res.errors.append("notifications.owner_opt_in: record who opted in to notifications, and when")

    # --- pricing ---
    if _get(cfg, "pricing", "approved_wording") is not None and _get(cfg, "pricing", "approved_by") is None:
        res.errors.append("pricing.approved_by: required when approved_wording is set")

    # --- languages ---
    supported = _get(cfg, "languages", "supported") or []
    if isinstance(supported, list) and "en" not in supported:
        res.errors.append("languages.supported: must include 'en'")
    if isinstance(supported, list) and "es" not in supported and _get(cfg, "languages", "other_language_line") is None:
        res.warnings.append("languages.other_language_line: not set, so Spanish-speaking callers get no fallback line yet")

    # --- data ---
    days = _get(cfg, "data", "retention_days")
    if isinstance(days, int) and not isinstance(days, bool) and not (1 <= days <= MAX_RETENTION_DAYS):
        res.errors.append(f"data.retention_days: must be between 1 and {MAX_RETENTION_DAYS}")

    # --- no undermining text anywhere (the changelog is excluded: it describes history) ---
    for path, s in _strings({k: v for k, v in cfg.items() if k != "changelog"}):
        for pattern, why in UNDERMINING:
            if pattern.search(s):
                res.errors.append(f"{path}: text {why}, which is not allowed in a client config: {s!r}")


# ---------- public API ----------

def validate_config_dict(cfg, folder_name=None, allow_todo=None):
    """Validate a parsed config. allow_todo defaults to True only for the template."""
    res = Result()
    if not isinstance(cfg, dict):
        res.errors.append("config must be a YAML mapping (key: value pairs)")
        return res
    _check(cfg, SCHEMA, "", res)
    _check_rules(cfg, folder_name, res)
    if allow_todo is None:
        allow_todo = cfg.get("client_id") == TEMPLATE_ID
    if res.todos:
        target = res.warnings if allow_todo else res.errors
        target.extend(f"unfinished: {t}" for t in res.todos)
    return res


def validate_private_dict(priv):
    res = Result()
    _check(priv, PRIVATE_SCHEMA, "private", res)
    return res


def load_client_config(config_path, require_private=False, allow_todo=None):
    """
    Load, validate, and (if needed) merge private contacts.
    Returns (config_or_None, Result). The config is None when there are errors.
    """
    config_path = Path(config_path)
    res = Result()
    try:
        cfg = load_yaml(config_path)
    except yaml.YAMLError as e:
        res.errors.append(f"YAML error: {e}")
        return None, res

    res = validate_config_dict(cfg, folder_name=config_path.parent.name, allow_todo=allow_todo)

    private_path = config_path.parent / "private" / "contacts.yaml"
    priv = {}
    if private_path.exists():
        try:
            priv = load_yaml(private_path) or {}
        except yaml.YAMLError as e:
            res.errors.append(f"private/contacts.yaml YAML error: {e}")
            priv = {}
        p_res = validate_private_dict(priv)
        res.errors.extend(p_res.errors)

    merged = copy.deepcopy(cfg) if isinstance(cfg, dict) else None
    if merged is not None:
        for (section, key), pkey in PRIVATE_FIELDS.items():
            val = _get(merged, section, key)
            uses_private = val == PRIVATE or (isinstance(val, list) and PRIVATE in val)
            if uses_private:
                if pkey in priv:
                    merged[section][key] = priv[pkey]
                elif require_private:
                    res.errors.append(f"{section}.{key}: set to PRIVATE but private/contacts.yaml has no '{pkey}'")

    return (merged if res.ok else None), res


def model_view(cfg):
    """
    The ONLY part of the config the model sees. Excludes phone numbers, emails,
    owner and approval records, retention, forwarding notes, and the changelog,
    so the model can't be tricked into revealing them.
    """
    b = cfg["business"]
    return {
        "business": {k: b[k] for k in ("name", "trade", "timezone", "service_area", "business_hours",
                                       "after_hours_definition", "services_offered", "services_not_offered")},
        "greeting": cfg["greeting"]["text"],
        "recording": {"stores_audio": cfg["recording"]["stores_audio"],
                      "stores_transcripts": cfg["recording"]["stores_transcripts"]},
        "languages": cfg["languages"],
        "extra_emergency_triggers": cfg["emergencies"]["extra_emergency_triggers"],
        "pricing_approved_wording": cfg["pricing"]["approved_wording"],
        "booking_enabled": cfg["booking"]["enabled"],
    }
