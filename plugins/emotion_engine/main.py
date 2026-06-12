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
        self.context.api.add_route("POST", "/state", self.update_state)
        self.context.api.add_route("POST", "/mood", self.set_mood)
        self.context.api.add_route("POST", "/feedback", self.feedback)
        self.context.api.add_route("POST", "/test-happy", self.test_happy)

    async def on_enable(self):
        self.context.events.subscribe("idle.nudge", self.on_idle_nudge)
        await self.context.log_console("INFO", "Emotion Engine plugin enabled")

    async def get_state(self, request):
        return {"ok": True, "state": self.state, "explanation": self.explain_mood()}

    async def update_state(self, request):
        payload = await request.json()
        before = dict(self.state)
        for key in ("happiness", "loneliness", "annoyance", "curiosity", "energy"):
            if key in payload:
                self.state[key] = max(0.0, min(1.0, float(payload[key])))
        if "mood" in payload:
            self.state["mood"] = str(payload["mood"])
        await self.context.events.emit("emotion.changed", {"before": before, "state": self.state, "reason": payload.get("reason", "manual_update")})
        return {"ok": True, "state": self.state, "explanation": self.explain_mood()}

    async def set_mood(self, request):
        payload = await request.json()
        mood = str(payload.get("mood", "")).strip()
        if not mood:
            return {"ok": False, "error": "mood is required"}
        before = self.state["mood"]
        self.state["mood"] = mood
        await self.context.events.emit("emotion.changed", {"before": before, "mood": mood, "reason": payload.get("reason", "manual_mood")})
        return {"ok": True, "state": self.state, "explanation": self.explain_mood()}

    async def feedback(self, request):
        payload = await request.json()
        signal = str(payload.get("signal", "neutral"))
        if signal == "positive":
            self.state["happiness"] = min(1.0, self.state["happiness"] + 0.1)
            self.state["annoyance"] = max(0.0, self.state["annoyance"] - 0.05)
        elif signal == "negative":
            self.state["annoyance"] = min(1.0, self.state["annoyance"] + 0.1)
            self.state["happiness"] = max(0.0, self.state["happiness"] - 0.05)
        await self.context.events.emit("emotion.feedback", {"signal": signal, "state": self.state})
        return {"ok": True, "state": self.state}

    async def test_happy(self, request):
        before = self.state["mood"]
        self.state["mood"] = "happy"
        self.state["happiness"] = min(1.0, self.state["happiness"] + 0.2)
        await self.context.events.emit("emotion.changed", {"before": before, "mood": "happy", "reason": "manual_test"})
        return {"ok": True, "state": self.state}

    async def on_idle_nudge(self, event):
        self.state["loneliness"] = min(1.0, self.state["loneliness"] + 0.02)
        self.state["energy"] = max(0.0, self.state["energy"] - 0.01)

    def explain_mood(self):
        mood = self.state.get("mood", "neutral")
        drivers = sorted(
            ((key, value) for key, value in self.state.items() if key != "mood"),
            key=lambda item: item[1],
            reverse=True,
        )[:2]
        driver_text = ", ".join(f"{key}={value:.2f}" for key, value in drivers)
        return f"Mood is {mood}; strongest signals: {driver_text}."


def setup(context):
    return Plugin(context)
