from buddycore.database import now_iso
from buddycore.plugins import BuddyPlugin


class Plugin(BuddyPlugin):
    async def on_load(self):
        self.context.api.add_route("GET", "/stats", self.stats)
        self.context.api.add_route("GET", "/memories", self.list_memories)
        self.context.api.add_route("POST", "/memories", self.create_memory)
        self.context.api.add_route("POST", "/memories/update", self.update_memory)
        self.context.api.add_route("POST", "/memories/delete", self.delete_memory)
        self.context.api.add_route("GET", "/export", self.export_memories)
        self.context.api.add_route("POST", "/import", self.import_memories)
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

    async def list_memories(self, request):
        limit = int(request.query_params.get("limit", 100))
        with self.context.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE enabled=1 ORDER BY importance DESC, updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return {"ok": True, "memories": [dict(row) for row in rows]}

    async def create_memory(self, request):
        payload = await request.json()
        content = str(payload.get("content", "")).strip()
        if not content:
            return {"ok": False, "error": "content is required"}
        now = now_iso()
        with self.context.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO memories (created_at, updated_at, memory_type, title, content, importance, confidence, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    now,
                    payload.get("memory_type", "durable"),
                    payload.get("title"),
                    content,
                    int(payload.get("importance", 5)),
                    float(payload.get("confidence", 1.0)),
                    payload.get("source", self.context.plugin_id),
                ),
            )
            memory_id = cur.lastrowid
        await self.context.events.emit("memory.created", {"id": memory_id, "title": payload.get("title")})
        return {"ok": True, "id": memory_id}

    async def update_memory(self, request):
        payload = await request.json()
        memory_id = int(payload.get("id", 0))
        allowed = {key: payload[key] for key in ("title", "content", "importance", "confidence", "enabled") if key in payload}
        if not memory_id or not allowed:
            return {"ok": False, "error": "id and at least one update field are required"}
        allowed["updated_at"] = now_iso()
        assignments = ", ".join(f"{key}=?" for key in allowed)
        values = list(allowed.values()) + [memory_id]
        with self.context.db.connect() as conn:
            conn.execute(f"UPDATE memories SET {assignments} WHERE id=?", values)
        await self.context.events.emit("memory.updated", {"id": memory_id})
        return {"ok": True, "id": memory_id}

    async def delete_memory(self, request):
        payload = await request.json()
        memory_id = int(payload.get("id", 0))
        if not memory_id:
            return {"ok": False, "error": "id is required"}
        with self.context.db.connect() as conn:
            conn.execute("UPDATE memories SET enabled=0, updated_at=? WHERE id=?", (now_iso(), memory_id))
        await self.context.events.emit("memory.deleted", {"id": memory_id})
        return {"ok": True, "id": memory_id}

    async def export_memories(self, request):
        with self.context.db.connect() as conn:
            rows = conn.execute("SELECT * FROM memories ORDER BY id").fetchall()
        return {"ok": True, "memories": [dict(row) for row in rows]}

    async def import_memories(self, request):
        payload = await request.json()
        memories = payload.get("memories", [])
        if not isinstance(memories, list):
            return {"ok": False, "error": "memories must be a list"}
        now = now_iso()
        imported = 0
        with self.context.db.connect() as conn:
            for item in memories:
                content = str(item.get("content", "")).strip()
                if not content:
                    continue
                conn.execute(
                    """
                    INSERT INTO memories (created_at, updated_at, memory_type, title, content, importance, confidence, source, enabled)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.get("created_at", now),
                        now,
                        item.get("memory_type", "imported"),
                        item.get("title"),
                        content,
                        int(item.get("importance", 5)),
                        float(item.get("confidence", 1.0)),
                        item.get("source", "import"),
                        1 if item.get("enabled", True) else 0,
                    ),
                )
                imported += 1
        await self.context.events.emit("memory.imported", {"count": imported})
        return {"ok": True, "imported": imported}


def setup(context):
    return Plugin(context)
