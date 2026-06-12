from __future__ import annotations

import asyncio
import importlib.util
import inspect
import logging
import re
import shutil
import subprocess
import tempfile
import traceback
import zipfile
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, FastAPI

from buddycore.database import BuddyDatabase, now_iso
from buddycore.events import EventBus
from buddycore.console import ConsoleHub
from buddycore.plugins.context import PluginContext
from buddycore.plugins.permissions import permission_risk


class PluginManager:
    def __init__(self, plugin_dir: Path, config_dir: Path, data_dir: Path, db: BuddyDatabase, event_bus: EventBus, console: ConsoleHub):
        self.plugin_dir = plugin_dir
        self.config_dir = config_dir
        self.data_dir = data_dir
        self.db = db
        self.event_bus = event_bus
        self.console = console
        self.router = APIRouter(prefix="/api/plugins")
        self.app: FastAPI | None = None
        self.plugins: dict[str, Any] = {}
        self.manifests: dict[str, dict[str, Any]] = {}
        self.contexts: dict[str, PluginContext] = {}
        self.logger = logging.getLogger("buddycore.plugins")
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        (self.config_dir / "plugins").mkdir(parents=True, exist_ok=True)

    def set_app(self, app: FastAPI) -> None:
        self.app = app

    async def startup(self, safe_mode: bool = False) -> None:
        self.logger.info("Scanning plugins in %s", self.plugin_dir)
        await self.rescan(register_only=False, safe_mode=safe_mode)

    async def rescan(self, register_only: bool = False, safe_mode: bool = False) -> list[dict[str, Any]]:
        discovered = []
        for plugin_path in sorted(self.plugin_dir.iterdir()):
            if not plugin_path.is_dir():
                continue
            manifest_path = plugin_path / "plugin.yaml"
            if not manifest_path.exists():
                continue
            try:
                manifest = self._load_manifest(manifest_path)
                plugin_id = manifest["id"]
                enabled_default = bool(manifest.get("enabled_by_default", False))
                self.db.upsert_plugin(manifest, str(plugin_path), enabled_default)
                self.manifests[plugin_id] = manifest
                discovered.append({"id": plugin_id, "name": manifest.get("name", plugin_id), "path": str(plugin_path)})
                self.logger.info("Discovered plugin: %s", plugin_id)
            except Exception as exc:
                self.logger.error("Failed to read plugin manifest %s: %s", manifest_path, exc)

        if register_only:
            return discovered

        rows = self.db.get_plugin_rows()
        for row in rows:
            plugin_id = row["id"]
            if safe_mode and plugin_id not in {"dashboard_terminal", "log_viewer", "system_monitor"}:
                self.logger.warning("Safe mode: skipping plugin %s", plugin_id)
                continue
            if row.get("enabled"):
                await self.load_plugin(plugin_id)
        return discovered

    def _load_manifest(self, manifest_path: Path) -> dict[str, Any]:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        required = ["id", "name", "version", "entrypoint"]
        missing = [key for key in required if key not in manifest]
        if missing:
            raise ValueError(f"Missing manifest keys: {', '.join(missing)}")
        return manifest

    def _load_plugin_config(self, plugin_id: str, plugin_path: Path) -> dict[str, Any]:
        default_path = plugin_path / "config.yaml"
        user_path = self.config_dir / "plugins" / f"{plugin_id}.yaml"
        default_config = yaml.safe_load(default_path.read_text(encoding="utf-8")) if default_path.exists() else {}
        user_config = yaml.safe_load(user_path.read_text(encoding="utf-8")) if user_path.exists() else {}
        return self._deep_merge(default_config or {}, user_config or {})

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        result = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    async def _maybe_call(self, plugin_id: str, obj: Any, method_name: str) -> None:
        method = getattr(obj, method_name, None)
        if not method:
            return
        try:
            result = method()
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            tb = traceback.format_exc()
            self.logger.error("Plugin %s failed during %s: %s", plugin_id, method_name, exc)
            self.db.record_plugin_error(plugin_id, method_name, type(exc).__name__, str(exc), tb)
            await self.console.publish({
                "kind": "error",
                "level": "ERROR",
                "source": "plugin_manager",
                "plugin_id": plugin_id,
                "message": f"Plugin {plugin_id} failed during {method_name}: {exc}",
            })
            raise

    async def load_plugin(self, plugin_id: str) -> bool:
        if plugin_id in self.plugins:
            return True
        row = self.db.get_plugin_row(plugin_id)
        if not row:
            self.logger.warning("Cannot load unknown plugin %s", plugin_id)
            return False
        plugin_path = Path(row["path"])
        manifest = self.manifests.get(plugin_id) or self._load_manifest(plugin_path / "plugin.yaml")
        entrypoint = plugin_path / manifest["entrypoint"]
        if not entrypoint.exists():
            self.db.set_plugin_status(plugin_id, "failed", f"Entrypoint missing: {entrypoint}")
            return False
        try:
            config = self._load_plugin_config(plugin_id, plugin_path)
            if self.app is None:
                raise RuntimeError("PluginManager app is not set")
            context = PluginContext(plugin_id, manifest, config, self.app, self.db, self.event_bus, self.console, self.data_dir)
            module_name = f"buddy_plugin_{plugin_id}_{abs(hash(str(entrypoint)))}"
            spec = importlib.util.spec_from_file_location(module_name, entrypoint)
            if not spec or not spec.loader:
                raise ImportError(f"Could not import plugin module {entrypoint}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if not hasattr(module, "setup"):
                raise AttributeError("Plugin must define setup(context)")
            plugin = module.setup(context)
            if inspect.isawaitable(plugin):
                plugin = await plugin
            self.plugins[plugin_id] = plugin
            self.contexts[plugin_id] = context
            self.manifests[plugin_id] = manifest
            await self._maybe_call(plugin_id, plugin, "on_load")
            await self._maybe_call(plugin_id, plugin, "on_enable")
            self.db.set_plugin_status(plugin_id, "running")
            self.logger.info("Plugin running: %s", plugin_id)
            await self.console.publish({
                "kind": "plugin",
                "level": "INFO",
                "source": "plugin_manager",
                "plugin_id": plugin_id,
                "message": f"Plugin running: {plugin_id}",
            })
            return True
        except Exception as exc:
            tb = traceback.format_exc()
            self.logger.error("Failed to load plugin %s: %s", plugin_id, exc)
            self.db.record_plugin_error(plugin_id, "load", type(exc).__name__, str(exc), tb)
            await self.console.publish({
                "kind": "error",
                "level": "ERROR",
                "source": "plugin_manager",
                "plugin_id": plugin_id,
                "message": f"Failed to load plugin {plugin_id}: {exc}",
            })
            return False

    async def enable_plugin(self, plugin_id: str) -> dict[str, Any]:
        self.db.set_plugin_enabled(plugin_id, True)
        ok = await self.load_plugin(plugin_id)
        return {"ok": ok, "plugin_id": plugin_id}

    async def disable_plugin(self, plugin_id: str) -> dict[str, Any]:
        await self.unload_plugin(plugin_id, call_disable=True, status="disabled")
        self.db.set_plugin_enabled(plugin_id, False)
        await self.console.publish({
            "kind": "plugin",
            "level": "WARN",
            "source": "plugin_manager",
            "plugin_id": plugin_id,
            "message": f"Plugin disabled: {plugin_id}",
        })
        return {"ok": True, "plugin_id": plugin_id}

    async def unload_plugin(self, plugin_id: str, call_disable: bool = False, status: str = "stopped") -> bool:
        plugin = self.plugins.get(plugin_id)
        if plugin:
            if call_disable:
                try:
                    await self._maybe_call(plugin_id, plugin, "on_disable")
                except Exception:
                    pass
            try:
                await self._maybe_call(plugin_id, plugin, "on_unload")
            except Exception:
                pass
        removed = self.event_bus.unsubscribe_plugin(plugin_id)
        self.plugins.pop(plugin_id, None)
        self.contexts.pop(plugin_id, None)
        self.db.set_plugin_status(plugin_id, status)
        self.logger.info("Plugin unloaded: %s (%s subscriptions removed)", plugin_id, removed)
        return bool(plugin)

    async def reload_plugin(self, plugin_id: str) -> dict[str, Any]:
        await self.unload_plugin(plugin_id, call_disable=True, status="reloading")
        self.db.set_plugin_enabled(plugin_id, True)
        ok = await self.load_plugin(plugin_id)
        return {"ok": ok, "plugin_id": plugin_id, "note": "Routes are not fully removed in v0.1 reload; restart service for a clean router."}

    async def shutdown(self) -> None:
        for plugin_id in list(self.plugins):
            await self.unload_plugin(plugin_id, call_disable=False, status="stopped")

    def list_plugins(self) -> list[dict[str, Any]]:
        rows = self.db.get_plugin_rows()
        errors = {e["plugin_id"]: e for e in self.db.get_plugin_errors(limit=50)}
        for row in rows:
            row["loaded"] = row["id"] in self.plugins
            row["recent_error"] = errors.get(row["id"])
        return rows

    def get_plugin_errors(self, plugin_id: str | None = None) -> list[dict[str, Any]]:
        return self.db.get_plugin_errors(plugin_id=plugin_id, limit=100)

    def get_plugin_events(self, plugin_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return self.db.recent_events(limit=limit, plugin_id=plugin_id)

    def get_plugin_permissions(self, plugin_id: str) -> list[dict[str, Any]]:
        permissions = self.db.get_plugin_permissions(plugin_id)
        for permission in permissions:
            permission["risk"] = permission_risk(str(permission.get("permission", "")))
            permission["granted"] = bool(permission.get("granted"))
            permission["required"] = bool(permission.get("required"))
        return permissions

    def set_plugin_permission(self, plugin_id: str, permission: str, granted: bool) -> bool:
        return self.db.set_plugin_permission(plugin_id, permission, granted)

    def get_plugin_detail(self, plugin_id: str) -> dict[str, Any] | None:
        row = self.db.get_plugin_row(plugin_id)
        if not row:
            return None
        plugin_path = Path(row["path"])
        manifest = self.manifests.get(plugin_id)
        if manifest is None and (plugin_path / "plugin.yaml").exists():
            manifest = self._load_manifest(plugin_path / "plugin.yaml")
        manifest = manifest or {}
        return {
            "plugin": {**row, "loaded": plugin_id in self.plugins},
            "manifest": manifest,
            "config": self._load_plugin_config(plugin_id, plugin_path),
            "permissions": self.get_plugin_permissions(plugin_id),
            "dependencies": self.detect_dependencies(manifest),
            "errors": self.get_plugin_errors(plugin_id)[:20],
            "events": self.get_plugin_events(plugin_id, limit=50),
        }

    def detect_dependencies(self, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        dependencies = self._manifest_python_dependencies(manifest)
        return [self._dependency_status(item) for item in dependencies]

    def _manifest_python_dependencies(self, manifest: dict[str, Any]) -> list[Any]:
        deps = manifest.get("python_dependencies") or manifest.get("requirements") or []
        nested = manifest.get("dependencies", {})
        if isinstance(nested, dict):
            deps = nested.get("python", deps)
        if isinstance(deps, (str, dict)):
            return [deps]
        if isinstance(deps, list):
            return deps
        return []

    def _dependency_status(self, item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            package = str(item.get("package") or item.get("name") or item.get("requirement") or "")
            module = str(item.get("module") or "") or self._infer_module_name(package)
            optional = bool(item.get("optional", False))
        else:
            package = str(item)
            module = self._infer_module_name(package)
            optional = False
        installed = bool(module and importlib.util.find_spec(module))
        return {
            "package": package,
            "module": module,
            "optional": optional,
            "installed": installed,
            "install_command": f"pip install {package}" if package else "",
        }

    def _infer_module_name(self, requirement: str) -> str:
        package = re.split(r"[<>=!~;\\[]", requirement, maxsplit=1)[0].strip()
        package = package.replace("-", "_")
        aliases = {
            "pyyaml": "yaml",
            "python_multipart": "multipart",
            "opencv_python": "cv2",
            "pillow": "PIL",
        }
        return aliases.get(package.lower(), package)

    async def install_from_zip(self, zip_path: Path) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="buddy_plugin_zip_") as tmp:
            tmp_path = Path(tmp)
            with zipfile.ZipFile(zip_path, "r") as zf:
                self._safe_extract_zip(zf, tmp_path)
            plugin_source = self._find_plugin_root(tmp_path)
            result = self._install_plugin_folder(plugin_source, source_type="zip", source_url=str(zip_path))
            await self.rescan(register_only=True)
            return result

    async def install_from_github(self, repo_url: str, branch: str = "main", subdir: str = "") -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="buddy_plugin_git_") as tmp:
            tmp_path = Path(tmp)
            cmd = ["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(tmp_path / "repo")]
            self.logger.info("Installing plugin from GitHub: %s", repo_url)
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            source = tmp_path / "repo" / subdir if subdir else tmp_path / "repo"
            plugin_source = self._find_plugin_root(source)
            result = self._install_plugin_folder(plugin_source, source_type="github", source_url=repo_url, source_branch=branch)
            await self.rescan(register_only=True)
            return result

    def _safe_extract_zip(self, zf: zipfile.ZipFile, target: Path) -> None:
        target_resolved = target.resolve()
        for member in zf.infolist():
            dest = (target / member.filename).resolve()
            if not str(dest).startswith(str(target_resolved)):
                raise ValueError(f"Unsafe ZIP path: {member.filename}")
        zf.extractall(target)

    def _find_plugin_root(self, root: Path) -> Path:
        if (root / "plugin.yaml").exists():
            return root
        candidates = [p for p in root.iterdir() if p.is_dir() and (p / "plugin.yaml").exists()]
        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            raise ValueError("No plugin.yaml found in plugin package")
        raise ValueError("Multiple plugin.yaml files found; specify a subdirectory")

    def _install_plugin_folder(self, source: Path, source_type: str, source_url: str, source_branch: str | None = None) -> dict[str, Any]:
        manifest = self._load_manifest(source / "plugin.yaml")
        plugin_id = manifest["id"]
        target = self.plugin_dir / plugin_id
        if target.exists():
            backup = self.plugin_dir / f"{plugin_id}.backup-{int(asyncio.get_event_loop().time())}"
            shutil.move(str(target), str(backup))
        shutil.copytree(source, target)
        self.db.upsert_plugin(manifest, str(target), False)
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE plugins SET source_type=?, source_url=?, source_branch=?, enabled=0, status='installed', updated_at=? WHERE id=?",
                (source_type, source_url, source_branch, now_iso(), plugin_id),
            )
        self.logger.info("Installed plugin %s from %s", plugin_id, source_type)
        return {
            "ok": True,
            "plugin_id": plugin_id,
            "name": manifest.get("name", plugin_id),
            "version": manifest.get("version"),
            "source_type": source_type,
            "enabled": False,
            "message": "Plugin installed disabled. Review permissions and enable manually.",
        }
