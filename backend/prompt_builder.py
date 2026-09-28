"""
Builds the system prompt the model receives, and loads .env settings.

The system prompt = the text between the BEGIN/END PROMPT markers in
prompts/base_system_prompt.md, with {{CLIENT_CONFIG}} replaced by the
MODEL-FACING part of the client's config (see config_schema.model_view).

The config is validated first. An invalid config raises ConfigError, and no
prompt is built.
"""

import os
from pathlib import Path

import yaml

from .config_schema import load_client_config, model_view

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_PROMPT = REPO_ROOT / "prompts" / "base_system_prompt.md"
TEMPLATE_CONFIG = REPO_ROOT / "clients" / "_template" / "config.yaml"

BEGIN, END, SLOT = "<!-- BEGIN PROMPT -->", "<!-- END PROMPT -->", "{{CLIENT_CONFIG}}"


class ConfigError(Exception):
    def __init__(self, path, errors):
        self.errors = errors
        super().__init__(f"Invalid client config {path}:\n" + "\n".join(f"  - {e}" for e in errors))


def build_system_prompt(config_path: Path = TEMPLATE_CONFIG, require_private: bool = False) -> str:
    text = BASE_PROMPT.read_text(encoding="utf-8")
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError(f"{BASE_PROMPT.name} must contain exactly one BEGIN and one END PROMPT marker.")
    prompt = text.split(BEGIN, 1)[1].split(END, 1)[0].strip()
    if prompt.count(SLOT) != 1:
        raise ValueError(f"The prompt must contain {SLOT} exactly once.")

    config, result = load_client_config(config_path, require_private=require_private)
    if not result.ok:
        raise ConfigError(config_path, result.errors)
    config_text = yaml.safe_dump(model_view(config), sort_keys=False, allow_unicode=True).strip()
    return prompt.replace(SLOT, config_text)


def load_dotenv(path: Path = REPO_ROOT / ".env") -> bool:
    """
    Read KEY=value lines from .env into the environment.
    Settings already in the environment win. Values are never printed.
    Returns False if there is no .env file.
    """
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return True
