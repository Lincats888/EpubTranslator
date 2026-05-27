import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "model": "deepseek-chat",
    "temperature": 0.3,
    "max_tokens": 2000,
    "code_selectors": ["pre", "code"],
    "output_mode": "bilingual",  # "bilingual" or "chinese_only"
}


def load_config(config_path: str | Path = "config.json") -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if "api_key" not in config or not config["api_key"]:
        raise ValueError("api_key is required in config.json")

    for key, default in DEFAULT_CONFIG.items():
        config.setdefault(key, default)

    return config
