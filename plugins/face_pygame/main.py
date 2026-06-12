from buddycore.plugins import BuddyPlugin


class Plugin(BuddyPlugin):
    def __init__(self, context):
        super().__init__(context)
        self.current_mood = "neutral"
        self.speaking = False
        self.debug_overlay = bool(self.config.get("settings", {}).get("debug_overlay", False))

    async def on_load(self):
        self.context.api.add_route("GET", "/status", self.status)
        self.context.api.add_route("POST", "/theme", self.set_theme)
        self.context.api.add_route("POST", "/debug-overlay", self.set_debug_overlay)
        self.context.api.add_route("POST", "/test-mood", self.test_mood)

    async def on_enable(self):
        self.context.events.subscribe("emotion.changed", self.on_emotion_changed)
        self.context.events.subscribe("face.set_mood", self.on_face_set_mood)
        self.context.events.subscribe("tts.started", self.on_tts_started)
        self.context.events.subscribe("tts.finished", self.on_tts_finished)
        await self.context.log_console("INFO", "Pygame Face plugin enabled in safe renderer mode")

    async def status(self, request):
        return {
            "ok": True,
            "current_mood": self.current_mood,
            "speaking": self.speaking,
            "debug_overlay": self.debug_overlay,
            "pygame_available": self.pygame_available(),
            "settings": self.config.get("settings", {}),
            "note": "Renderer state is ready; fullscreen drawing should only start when configured on the Pi display.",
        }

    async def set_theme(self, request):
        payload = await request.json()
        theme = str(payload.get("theme", "")).strip()
        if not theme:
            return {"ok": False, "error": "theme is required"}
        self.config.setdefault("settings", {})["theme"] = theme
        await self.context.events.emit("face.theme_changed", {"theme": theme})
        return {"ok": True, "theme": theme}

    async def set_debug_overlay(self, request):
        payload = await request.json()
        self.debug_overlay = bool(payload.get("enabled", False))
        await self.context.events.emit("face.debug_overlay", {"enabled": self.debug_overlay})
        return {"ok": True, "debug_overlay": self.debug_overlay}

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

    async def on_tts_started(self, event):
        self.speaking = True

    async def on_tts_finished(self, event):
        self.speaking = False

    def pygame_available(self):
        try:
            import pygame  # noqa: F401
            return True
        except Exception:
            return False


def setup(context):
    return Plugin(context)
