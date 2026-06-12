from __future__ import annotations

import inspect
import logging
import traceback
from collections import defaultdict
from typing import Any, Awaitable, Callable

from .database import BuddyDatabase
from .console import ConsoleHub

EventHandler = Callable[[dict[str, Any]], Awaitable[None] | None]


class EventBus:
    def __init__(self, db: BuddyDatabase, console: ConsoleHub):
        self.db = db
        self.console = console
        self._subscribers: dict[str, list[tuple[str, EventHandler]]] = defaultdict(list)
        self.logger = logging.getLogger("buddycore.events")

    def subscribe(self, event_type: str, handler: EventHandler, plugin_id: str = "core") -> None:
        self._subscribers[event_type].append((plugin_id, handler))
        self.logger.debug("Subscribed %s to %s", plugin_id, event_type)

    def unsubscribe_plugin(self, plugin_id: str) -> int:
        removed = 0
        for event_type in list(self._subscribers):
            before = len(self._subscribers[event_type])
            self._subscribers[event_type] = [
                item for item in self._subscribers[event_type] if item[0] != plugin_id
            ]
            removed += before - len(self._subscribers[event_type])
            if not self._subscribers[event_type]:
                del self._subscribers[event_type]
        if removed:
            self.logger.debug("Unsubscribed %s handlers for plugin %s", removed, plugin_id)
        return removed

    async def emit(self, event_type: str, payload: dict[str, Any] | None = None, source: str = "core") -> None:
        payload = payload or {}
        message = f"Event emitted: {event_type}"
        self.logger.debug(message)
        self.db.log_event("EVENT", source, message, event_type=event_type, payload=payload, plugin_id=source if source != "core" else None)
        await self.console.publish({
            "kind": "event",
            "level": "EVENT",
            "source": source,
            "plugin_id": source if source != "core" else None,
            "event_type": event_type,
            "message": message,
            "payload": payload,
        })

        handlers = list(self._subscribers.get(event_type, [])) + list(self._subscribers.get("*", []))
        for plugin_id, handler in handlers:
            try:
                result = handler({"type": event_type, "source": source, "payload": payload})
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                tb = traceback.format_exc()
                self.logger.error("Plugin %s failed while handling event %s: %s", plugin_id, event_type, exc)
                self.db.record_plugin_error(plugin_id, "event_handler", type(exc).__name__, str(exc), tb, event_type=event_type, payload=payload)
                await self.console.publish({
                    "kind": "error",
                    "level": "ERROR",
                    "source": "event_bus",
                    "plugin_id": plugin_id,
                    "event_type": event_type,
                    "message": f"Plugin {plugin_id} failed while handling {event_type}: {exc}",
                })
