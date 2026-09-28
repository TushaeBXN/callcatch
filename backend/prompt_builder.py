"""
Builds the system prompt the model receives, and loads .env settings.

The system prompt = the text between the BEGIN/END PROMPT markers in
prompts/base_system_prompt.md, with {{CLIENT_CONFIG}} replaced by the
client's config.yaml.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_PROMPT = REPO_ROOT / "prompts" / "base_system_prompt.md"
TEMPLATE_CONFIG = REPO_ROOT / "clients" / "_template" / "config.yaml"

BEGIN, END, SLOT = "<!-- BEGIN PROMPT -->", "<!-- END PROMPT -->", "{{CLIENT_CONFIG}}"


def build_system_prompt(config_path: Path = TEMPLATE_CONFIG) -> str:
    text = BASE_PROMPT.read_text(encoding="utf-8")
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError(f"{BASE_PROMPT.name} must contain exactly one BEGIN and one END PROMPT marker.")
    prompt = text.split(BEGIN, 1)[1].split(END, 1)[0].strip()
    if prompt.count(SLOT) != 1:
        raise ValueError(f"The prompt must contain {SLOT} exactly once.")
    config_text = Path(config_path).read_text(encoding="utf-8").strip()
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
