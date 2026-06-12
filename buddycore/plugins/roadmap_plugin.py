from __future__ import annotations

import importlib.util
from typing import Any

from buddycore.plugins import BuddyPlugin


class RoadmapPlugin(BuddyPlugin):
    """Safe foundation for hardware/cloud plugins that need later setup."""

    plugin_kind = "roadmap"
    readiness_note = "Installed and waiting for configuration."

    def __init__(self, context):
        super().__init__(context)
        self.ready = bool(self.config.get("settings", {}).get("enabled", False))

    async def on_load(self):
        self.context.api.add_route("GET", "/status", self.status)
        self.context.api.add_route("GET", "/setup-check", self.setup_check)
        self.context.api.add_route("POST", "/test-event", self.test_event)

    async def on_enable(self):
        await self.context.log_console("INFO", f"{self.context.manifest.get('name', self.context.plugin_id)} loaded")

    async def status(self, request):
        return {
            "ok": True,
            "plugin_id": self.context.plugin_id,
            "kind": self.plugin_kind,
            "ready": self.ready,
            "note": self.readiness_note,
            "settings": self.config.get("settings", {}),
        }

    async def setup_check(self, request):
        dependencies = self.context.manifest.get("dependencies", {}).get("python", [])
        if isinstance(dependencies, str):
            dependencies = [dependencies]
        checks = []
        for dep in dependencies:
            if isinstance(dep, dict):
                package = dep.get("package") or dep.get("name") or dep.get("requirement") or ""
                module = dep.get("module") or package
                optional = bool(dep.get("optional", False))
            else:
                package = str(dep)
                module = str(dep).split("==", 1)[0].split(">=", 1)[0].replace("-", "_")
                optional = False
            checks.append({
                "package": package,
                "module": module,
                "optional": optional,
                "installed": bool(module and importlib.util.find_spec(module)),
            })
        return {"ok": True, "ready": self.ready, "checks": checks}

    async def test_event(self, request):
        await self.context.events.emit(f"{self.context.plugin_id}.test", {"ready": self.ready})
        return {"ok": True, "event": f"{self.context.plugin_id}.test"}
