from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .config import ROOT_DIR, load_config, path_from_config
from .console import ConsoleHub
from .database import BuddyDatabase
from .events import EventBus
from .logging_setup import setup_logging
from .plugins.manager import PluginManager


class GitHubInstallRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    subdir: str = ""


def create_app() -> FastAPI:
    config = load_config()
    data_dir = path_from_config(config, "data_dir")
    log_dir = path_from_config(config, "log_dir")
    plugin_dir = path_from_config(config, "plugin_dir")
    config_dir = path_from_config(config, "config_dir")

    data_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    plugin_dir.mkdir(parents=True, exist_ok=True)

    console = ConsoleHub(max_lines=int(config.get("webui", {}).get("console_max_lines", 500)))
    logger = setup_logging(
        log_dir=log_dir,
        level=str(config.get("logging", {}).get("level", "INFO")),
        max_file_mb=int(config.get("logging", {}).get("max_file_mb", 10)),
        backup_count=int(config.get("logging", {}).get("backup_count", 10)),
        hub=console,
    )

    db = BuddyDatabase(data_dir / "buddy.db")
    db.init_schema()
    db.log_event("INFO", "core", "BuddyCore database initialized", event_type="system.database_ready")

    event_bus = EventBus(db, console)
    plugin_manager = PluginManager(plugin_dir, config_dir, data_dir, db, event_bus, console)

    app = FastAPI(title="BuddyCore", version=__version__)
    app.state.config = config
    app.state.console = console
    app.state.db = db
    app.state.event_bus = event_bus
    app.state.plugin_manager = plugin_manager
    app.state.logger = logger
    plugin_manager.set_app(app)

    web_static = ROOT_DIR / "buddycore" / "web" / "static"
    app.mount("/static", StaticFiles(directory=str(web_static)), name="static")

    @app.on_event("startup")
    async def startup() -> None:
        safe_mode = bool(config.get("system", {}).get("safe_mode", False))
        if safe_mode:
            logger.warning("BuddyCore starting in SAFE MODE")
            await console.publish({
                "kind": "system",
                "level": "WARN",
                "source": "core",
                "message": "BuddyCore starting in SAFE MODE",
            })
        logger.info("BuddyCore v%s starting", __version__)
        await event_bus.emit("system.started", {"version": __version__, "safe_mode": safe_mode}, source="core")
        await plugin_manager.startup(safe_mode=safe_mode)

    @app.on_event("shutdown")
    async def shutdown() -> None:
        logger.warning("BuddyCore shutting down")
        await event_bus.emit("system.shutdown", {}, source="core")

    @app.get("/")
    async def index():
        return FileResponse(web_static / "index.html")

    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        plugin_rows = plugin_manager.list_plugins()
        running = sum(1 for p in plugin_rows if p.get("status") == "running")
        enabled = sum(1 for p in plugin_rows if p.get("enabled"))
        return {
            "ok": True,
            "name": config.get("system", {}).get("name", "Buddy"),
            "version": __version__,
            "safe_mode": bool(config.get("system", {}).get("safe_mode", False)),
            "plugins": {
                "total": len(plugin_rows),
                "enabled": enabled,
                "running": running,
            },
        }

    @app.websocket("/ws/console")
    async def websocket_console(websocket: WebSocket):
        await console.connect(websocket)
        try:
            while True:
                # Keep the socket open. Clients may send pings/filters later.
                await websocket.receive_text()
        except WebSocketDisconnect:
            await console.disconnect(websocket)
        except Exception:
            await console.disconnect(websocket)

    @app.get("/api/logs/recent")
    async def recent_logs(limit: int = 200):
        return {"ok": True, "logs": console.recent(limit=limit)}

    @app.get("/api/events/recent")
    async def recent_events(limit: int = 100):
        return {"ok": True, "events": db.recent_events(limit=limit)}

    @app.get("/api/plugins")
    async def list_plugins():
        return {"ok": True, "plugins": plugin_manager.list_plugins()}

    @app.post("/api/plugins/rescan")
    async def rescan_plugins():
        discovered = await plugin_manager.rescan(register_only=True)
        return {"ok": True, "discovered": discovered, "plugins": plugin_manager.list_plugins()}

    @app.post("/api/plugins/{plugin_id}/enable")
    async def enable_plugin(plugin_id: str):
        result = await plugin_manager.enable_plugin(plugin_id)
        return result

    @app.post("/api/plugins/{plugin_id}/disable")
    async def disable_plugin(plugin_id: str):
        result = await plugin_manager.disable_plugin(plugin_id)
        return result

    @app.post("/api/plugins/{plugin_id}/reload")
    async def reload_plugin(plugin_id: str):
        result = await plugin_manager.reload_plugin(plugin_id)
        return result

    @app.get("/api/plugins/{plugin_id}/errors")
    async def plugin_errors(plugin_id: str):
        return {"ok": True, "errors": plugin_manager.get_plugin_errors(plugin_id)}

    @app.post("/api/plugins/install/zip")
    async def install_plugin_zip(file: UploadFile = File(...)):
        if not file.filename or not file.filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail="Upload must be a .zip file")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(await file.read())
        try:
            result = await plugin_manager.install_from_zip(tmp_path)
            return result
        finally:
            try:
                tmp_path.unlink()
            except Exception:
                pass

    @app.post("/api/plugins/install/github")
    async def install_plugin_github(payload: GitHubInstallRequest):
        try:
            return await plugin_manager.install_from_github(payload.repo_url, payload.branch, payload.subdir)
        except Exception as exc:
            logging.getLogger("buddycore.plugins.install").exception("GitHub plugin install failed")
            return {"ok": False, "error": str(exc)}

    app.include_router(plugin_manager.router)
    return app


app = create_app()


def main() -> None:
    config = load_config()
    host = str(config.get("system", {}).get("host", "0.0.0.0"))
    port = int(config.get("system", {}).get("port", 8080))
    uvicorn.run("buddycore.app:app", host=host, port=port, reload=False)
