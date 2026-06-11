from buddycore.plugins import BuddyPlugin


class Plugin(BuddyPlugin):
    async def on_load(self):
        self.context.api.add_route("GET", "/status", self.status)

    async def on_enable(self):
        await self.context.log_console("INFO", "Dashboard Terminal plugin online")

    async def status(self, request):
        return {
            "ok": True,
            "plugin": self.context.plugin_id,
            "theme": self.config.get("settings", {}).get("theme", "retro_terminal"),
            "message": "Dashboard terminal is glowing ominously, as requested.",
        }


def setup(context):
    return Plugin(context)
