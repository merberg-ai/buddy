from __future__ import annotations

from buddycore.config import CONFIG_FILE
from buddycore.debug_bundle import _redact
from buddycore.plugins import BuddyPlugin


class Plugin(BuddyPlugin):
    async def on_load(self):
        self.context.api.add_route("GET", "/core", self.core_config)
        self.context.api.add_route("GET", "/plugins", self.plugin_configs)

    async def on_enable(self):
        await self.context.log_console("INFO", "Config Manager plugin online")

    async def core_config(self, request):
        redact = bool(self.config.get("settings", {}).get("redact_sensitive_values", True))
        payload = getattr(request.app.state, "config", {}) or {}
        return {"ok": True, "path": str(CONFIG_FILE), "config": _redact(payload) if redact else payload}

    async def plugin_configs(self, request):
        rows = self.context.db.get_plugin_rows()
        return {
            "ok": True,
            "plugins": [
                {"id": row["id"], "name": row["name"], "enabled": bool(row["enabled"]), "status": row["status"]}
                for row in rows
            ],
        }


def setup(context):
    return Plugin(context)
