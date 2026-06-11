from buddycore.database import now_iso
from buddycore.plugins import BuddyPlugin


class Plugin(BuddyPlugin):
    async def on_load(self):
        self.context.api.add_route("GET", "/stats", self.stats)
        self.context.api.add_route("POST", "/test-memory", self.test_memory)

    async def on_enable(self):
        await self.context.log_console("INFO", "SQLite Memory plugin online")

    async def stats(self, request):
        with self.context.db.connect() as conn:
            memories = conn.execute("SELECT COUNT(*) AS c FROM memories").fetchone()["c"]
            messages = conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()["c"]
            events = conn.execute("SELECT COUNT(*) AS c FROM event_log").fetchone()["c"]
        return {"ok": True, "memories": memories, "messages": messages, "events": events}

    async def test_memory(self, request):
        with self.context.db.connect() as conn:
            conn.execute(
                "INSERT INTO memories (created_at, updated_at, memory_type, title, content, importance, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (now_iso(), now_iso(), "system", "Test memory", "Buddy memory system test entry.", 1, self.context.plugin_id),
            )
        await self.context.events.emit("memory.created", {"source": self.context.plugin_id, "title": "Test memory"})
        return {"ok": True, "message": "Test memory saved"}


def setup(context):
    return Plugin(context)
