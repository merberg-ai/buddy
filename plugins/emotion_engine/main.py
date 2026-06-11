from buddycore.plugins import BuddyPlugin


class Plugin(BuddyPlugin):
    def __init__(self, context):
        super().__init__(context)
        self.state = {
            "mood": self.config.get("settings", {}).get("default_mood", "neutral"),
            "happiness": 0.5,
            "loneliness": 0.0,
            "annoyance": 0.0,
            "curiosity": 0.5,
            "energy": 0.6,
        }

    async def on_load(self):
        self.context.api.add_route("GET", "/state", self.get_state)
        self.context.api.add_route("POST", "/test-happy", self.test_happy)

    async def on_enable(self):
        await self.context.log_console("INFO", "Emotion Engine plugin stub enabled")

    async def get_state(self, request):
        return {"ok": True, "state": self.state}

    async def test_happy(self, request):
        before = self.state["mood"]
        self.state["mood"] = "happy"
        self.state["happiness"] = min(1.0, self.state["happiness"] + 0.2)
        await self.context.events.emit("emotion.changed", {"before": before, "mood": "happy", "reason": "manual_test"})
        return {"ok": True, "state": self.state}


def setup(context):
    return Plugin(context)
