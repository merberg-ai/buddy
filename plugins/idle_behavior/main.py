from buddycore.plugins import BuddyPlugin


class Plugin(BuddyPlugin):
    def __init__(self, context):
        super().__init__(context)
        self.last_idle_mood = self.config.get("settings", {}).get("default_idle_mood", "calm")

    async def on_load(self):
        self.context.api.add_route("GET", "/status", self.status)
        self.context.api.add_route("POST", "/nudge", self.nudge)

    async def on_enable(self):
        await self.context.log_console("INFO", "Idle Behavior plugin online")

    async def status(self, request):
        return {"ok": True, "idle_mood": self.last_idle_mood, "settings": self.config.get("settings", {})}

    async def nudge(self, request):
        self.last_idle_mood = self.config.get("settings", {}).get("default_idle_mood", "calm")
        await self.context.events.emit("idle.nudge", {"mood": self.last_idle_mood})
        await self.context.events.emit("face.set_mood", {"mood": self.last_idle_mood, "reason": "idle_nudge"})
        return {"ok": True, "mood": self.last_idle_mood}


def setup(context):
    return Plugin(context)
