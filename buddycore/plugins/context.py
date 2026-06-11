from __future__ import annotations

import inspect
import logging
import traceback
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, Request

from buddycore.database import BuddyDatabase
from buddycore.events import EventBus
from buddycore.console import ConsoleHub


class PluginApi:
    def __init__(self, plugin_id: str, app: FastAPI, db: BuddyDatabase):
        self.plugin_id = plugin_id
        self.app = app
        self.db = db
        self.logger = logging.getLogger(f"plugin.{plugin_id}.api")

    def add_route(self, method: str, path: str, handler: Callable, **kwargs: Any) -> None:
        method = method.upper()
        safe_path = path if path.startswith("/") else f"/{path}"

        async def guarded_endpoint(request: Request):
            try:
                result = handler(request)
                if inspect.isawaitable(result):
                    result = await result
                return result
            except Exception as exc:
                tb = traceback.format_exc()
                self.logger.error("Plugin API endpoint failed %s %s: %s", method, safe_path, exc)
                self.db.record_plugin_error(self.plugin_id, "api_route", type(exc).__name__, str(exc), tb)
                return {
                    "ok": False,
                    "error": "Plugin endpoint failed",
                    "plugin_id": self.plugin_id,
                    "detail": str(exc),
                }

        full_path = f"/api/plugins/{self.plugin_id}{safe_path}"
        self.app.add_api_route(full_path, guarded_endpoint, methods=[method], **kwargs)
        self.logger.info("Registered plugin API route %s %s", method, full_path)


class PluginStorage:
    def __init__(self, plugin_id: str, data_dir: Path):
        self.plugin_id = plugin_id
        self.data_dir = data_dir / "plugin_data" / plugin_id
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def path(self, *parts: str) -> Path:
        return self.data_dir.joinpath(*parts)


class PluginEvents:
    def __init__(self, plugin_id: str, event_bus: EventBus):
        self.plugin_id = plugin_id
        self.event_bus = event_bus

    def subscribe(self, event_type: str, handler):
        self.event_bus.subscribe(event_type, handler, plugin_id=self.plugin_id)

    async def emit(self, event_type: str, payload: dict[str, Any] | None = None):
        await self.event_bus.emit(event_type, payload or {}, source=self.plugin_id)


class PluginContext:
    def __init__(
        self,
        plugin_id: str,
        manifest: dict[str, Any],
        config: dict[str, Any],
        app: FastAPI,
        db: BuddyDatabase,
        event_bus: EventBus,
        console: ConsoleHub,
        data_dir: Path,
    ):
        self.plugin_id = plugin_id
        self.manifest = manifest
        self.config = config
        self.db = db
        self.console = console
        self.logger = logging.getLogger(f"plugin.{plugin_id}")
        self.api = PluginApi(plugin_id, app, db)
        self.events = PluginEvents(plugin_id, event_bus)
        self.storage = PluginStorage(plugin_id, data_dir)

    async def log_console(self, level: str, message: str, payload: dict[str, Any] | None = None):
        await self.console.publish({
            "kind": "plugin",
            "level": level.upper(),
            "source": f"plugin.{self.plugin_id}",
            "plugin_id": self.plugin_id,
            "message": message,
            "payload": payload or {},
        })
