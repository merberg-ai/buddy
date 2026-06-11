from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "buddy.yaml"
CONFIG_EXAMPLE = CONFIG_DIR / "buddy.yaml.example"

DEFAULT_CONFIG: dict[str, Any] = {
    "system": {
        "name": "Buddy",
        "version": "0.1.0-framework",
        "host": "0.0.0.0",
        "port": 8080,
        "safe_mode": False,
    },
    "paths": {
        "data_dir": "data",
        "log_dir": "logs",
        "plugin_dir": "plugins",
        "config_dir": "config",
    },
    "logging": {
        "level": "INFO",
        "max_file_mb": 10,
        "backup_count": 10,
        "live_console_enabled": True,
        "sqlite_event_log_enabled": True,
    },
    "plugins": {
        "auto_discover": True,
        "auto_disable_repeated_failures": True,
        "max_errors": 5,
        "error_window_seconds": 300,
    },
    "webui": {
        "theme": "retro_terminal",
        "console_max_lines": 500,
    },
}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def ensure_config() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "plugins").mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        if CONFIG_EXAMPLE.exists():
            shutil.copy(CONFIG_EXAMPLE, CONFIG_FILE)
        else:
            CONFIG_FILE.write_text(yaml.safe_dump(DEFAULT_CONFIG, sort_keys=False), encoding="utf-8")


def load_config() -> dict[str, Any]:
    ensure_config()
    try:
        user_config = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        user_config = {}
    config = deep_merge(DEFAULT_CONFIG, user_config)

    # Environment overrides are handy for systemd and dev.
    if os.environ.get("BUDDY_HOST"):
        config["system"]["host"] = os.environ["BUDDY_HOST"]
    if os.environ.get("BUDDY_PORT"):
        config["system"]["port"] = int(os.environ["BUDDY_PORT"])
    if os.environ.get("BUDDY_SAFE_MODE"):
        config["system"]["safe_mode"] = os.environ["BUDDY_SAFE_MODE"].lower() in {"1", "true", "yes"}

    safe_flag = CONFIG_DIR / "safe_mode.flag"
    if safe_flag.exists():
        config["system"]["safe_mode"] = True

    return config


def path_from_config(config: dict[str, Any], key: str) -> Path:
    value = config.get("paths", {}).get(key)
    if not value:
        raise KeyError(f"Missing paths.{key} in config")
    p = Path(value)
    if not p.is_absolute():
        p = ROOT_DIR / p
    return p
