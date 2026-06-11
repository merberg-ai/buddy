from buddycore.plugins import BuddyPlugin


class Plugin(BuddyPlugin):
    def __init__(self, context):
        super().__init__(context)
        self.current_mood = "neutral"

    async def on_load(self):
        self.context.api.add_route("GET", "/status", self.status)
        self.context.api.add_route("POST", "/test-mood", self.test_mood)

    async def on_enable(self):
        self.context.events.subscribe("emotion.changed", self.on_emotion_changed)
        self.context.events.subscribe("face.set_mood", self.on_face_set_mood)
        await self.context.log_console("INFO", "Pygame Face plugin stub enabled")

    async def status(self, request):
        return {"ok": True, "current_mood": self.current_mood, "note": "Pygame renderer will be implemented in a later milestone."}

    async def test_mood(self, request):
        self.current_mood = "curious"
        await self.context.events.emit("face.mood_applied", {"mood": self.current_mood})
        return {"ok": True, "mood": self.current_mood}

    async def on_emotion_changed(self, event):
        self.current_mood = event.get("payload", {}).get("mood", self.current_mood)
        self.logger.info("Face mood changed to %s", self.current_mood)

    async def on_face_set_mood(self, event):
        self.current_mood = event.get("payload", {}).get("mood", self.current_mood)
        self.logger.info("Face set mood to %s", self.current_mood)


def setup(context):
    return Plugin(context)
