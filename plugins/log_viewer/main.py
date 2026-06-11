from buddycore.plugins import BuddyPlugin


class Plugin(BuddyPlugin):
    async def on_load(self):
        self.context.api.add_route("GET", "/recent", self.recent)
        self.context.api.add_route("GET", "/events", self.events)

    async def on_enable(self):
        await self.context.log_console("INFO", "Log Viewer plugin online")

    async def recent(self, request):
        limit = int(request.query_params.get("limit", self.config.get("settings", {}).get("default_limit", 200)))
        return {"ok": True, "logs": self.context.console.recent(limit=limit)}

    async def events(self, request):
        limit = int(request.query_params.get("limit", 100))
        return {"ok": True, "events": self.context.db.recent_events(limit=limit)}


def setup(context):
    return Plugin(context)
