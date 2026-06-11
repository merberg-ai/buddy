from buddycore.plugins import BuddyPlugin


class Plugin(BuddyPlugin):
    async def on_load(self):
        self.context.api.add_route("GET", "/status", self.status)
        self.context.api.add_route("POST", "/poke", self.poke)

    async def on_enable(self):
        self.context.events.subscribe("system.started", self.on_system_started)
        await self.context.log_console("INFO", "Example plugin enabled")

    async def status(self, request):
        return {"ok": True, "greeting": self.config.get("settings", {}).get("greeting", "Hello")}

    async def poke(self, request):
        await self.context.events.emit("face.set_mood", {"mood": "curious", "reason": "example_plugin_poke"})
        return {"ok": True, "message": "Poked. Mood event emitted."}

    async def on_system_started(self, event):
        self.logger.info("Example plugin saw system.started")


def setup(context):
    return Plugin(context)
