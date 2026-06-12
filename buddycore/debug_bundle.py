from __future__ import annotations

import json
import platform
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .console import ConsoleHub
from .database import BuddyDatabase


SENSITIVE_KEY_PARTS = ("api_key", "apikey", "key", "token", "secret", "password", "passwd")


def _redact(value: Any, key_name: str = "") -> Any:
    lowered = key_name.lower()
    if any(part in lowered for part in SENSITIVE_KEY_PARTS):
        return "[redacted]"
    if isinstance(value, dict):
        return {key: _redact(child, str(key)) for key, child in value.items()}
    if isinstance(value, list):
        return [_redact(child, key_name) for child in value]
    return value


def _write_json(zf: zipfile.ZipFile, name: str, payload: Any) -> None:
    zf.writestr(name, json.dumps(payload, indent=2, sort_keys=True, default=str))


def _add_file_if_exists(zf: zipfile.ZipFile, source: Path, archive_name: str) -> None:
    if source.exists() and source.is_file():
        zf.write(source, archive_name)


def create_debug_bundle(
    output_dir: Path,
    root_dir: Path,
    log_dir: Path,
    config: dict[str, Any],
    db: BuddyDatabase,
    console: ConsoleHub,
    plugins: list[dict[str, Any]],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    bundle_path = output_dir / f"buddy-debug-{stamp}.zip"

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _write_json(
            zf,
            "system.json",
            {
                "buddy_version": __version__,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "python": platform.python_version(),
                "platform": platform.platform(),
                "machine": platform.machine(),
            },
        )
        _write_json(zf, "config.redacted.json", _redact(config))
        _write_json(zf, "plugins.json", plugins)
        _write_json(zf, "events.recent.json", db.recent_events(limit=500))
        _write_json(zf, "plugin_errors.recent.json", db.get_plugin_errors(limit=200))
        _write_json(zf, "console.recent.json", console.recent(limit=500))

        for filename in ("README.md", "roadmap.txt", "requirements.txt"):
            _add_file_if_exists(zf, root_dir / filename, filename)

        for log_file in sorted(log_dir.glob("*.log*")):
            if log_file.is_file():
                zf.write(log_file, f"logs/{log_file.name}")

    return bundle_path
