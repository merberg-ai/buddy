# Buddy v1.0 Framework

**Buddy** is a Raspberry Pi 5 desktop AI buddy framework designed for Raspberry Pi OS Lite. The goal is a modular, plugin-first AI companion with a Pygame HDMI face display, a retro-terminal WebUI, SQLite memory, full logging, and safe plugin isolation.

This repository is the **initial GitHub-ready framework**: repo layout, install scripts, systemd service scripts, plugin manager, live WebUI console, SQLite database bootstrap, bundled starter plugins, and a roadmap.

> BuddyCore should stay boring. Plugins do the weird stuff.

---

## Current framework features

- FastAPI backend
- Responsive retro-terminal WebUI dashboard
- Live WebSocket console
- Structured logging with rotating log files
- SQLite database bootstrap
- Plugin discovery from `plugins/`
- Plugin enable/disable/reload/rescan
- Plugin status and error isolation
- Plugin API endpoint registration
- Install plugins from ZIP
- Install plugins from GitHub repo
- Default bundled plugin stubs
- Verbose colorized install scripts
- Run as a normal app or install as a systemd service
- Safe-mode flag support planned into the layout

---

## Target hardware

Recommended:

- Raspberry Pi 5
- Raspberry Pi OS Lite 64-bit
- HDMI display or HDMI touch display
- USB microphone or USB audio device
- USB camera or Pi camera
- Optional PCA9685 servo controller
- Optional LAN Ollama host
- Optional OpenAI API key

The framework can also run on a desktop/laptop for development.

---

## Quick start

```bash
git clone https://github.com/YOUR-USER/buddy.git
cd buddy
chmod +x scripts/*.sh
./scripts/install.sh
./scripts/run.sh
```

Then open:

```text
http://<pi-ip>:8080
```

For local testing on the Pi itself:

```text
http://127.0.0.1:8080
```

---

## Install as a system service

After running the installer:

```bash
./scripts/service-install.sh
```

Then manage Buddy with:

```bash
sudo systemctl status buddycore --no-pager
sudo systemctl restart buddycore
sudo systemctl stop buddycore
```

To uninstall the service:

```bash
./scripts/service-uninstall.sh
```

---

## Running manually

```bash
./scripts/run.sh
```

Or directly:

```bash
source .venv/bin/activate
python -m buddycore
```

Environment variables:

```bash
BUDDY_HOST=0.0.0.0 BUDDY_PORT=8080 python -m buddycore
```

---

## Project layout

```text
buddy/
  buddycore/                 Core app, event bus, logging, database, plugin manager
  plugins/                   Drop-in bundled and third-party plugins
  config/                    Main config and per-plugin configs
  data/                      Runtime database and plugin data
  logs/                      Rotating log files
  scripts/                   Install/run/service helper scripts
  systemd/                   systemd service template
  README.md
  roadmap.txt
  requirements.txt
```

---

## Plugin system

Plugins live in `plugins/<plugin_id>/` and must include a `plugin.yaml` manifest.

Example:

```text
plugins/example_plugin/
  plugin.yaml
  main.py
  config.yaml
```

A plugin can:

- Register API endpoints
- Register WebUI metadata
- Listen for events
- Emit events
- Have its own config
- Use plugin-scoped storage
- Log to Buddy's live console
- Fail without crashing BuddyCore

A plugin should not:

- Assume hardware exists
- Crash BuddyCore
- Silently install dependencies
- Control motion/vision/memory without declared permissions

---

## Installing plugins

### From ZIP

Use the WebUI plugin manager, or POST to:

```text
POST /api/plugins/install/zip
```

ZIP layout can be either:

```text
plugin.zip
  plugin.yaml
  main.py
```

or:

```text
plugin.zip
  my_plugin/
    plugin.yaml
    main.py
```

Installed plugins are not automatically enabled.

### From GitHub

Use the WebUI plugin manager, or POST JSON to:

```text
POST /api/plugins/install/github
```

Example payload:

```json
{
  "repo_url": "https://github.com/example/buddy-plugin-weather.git",
  "branch": "main",
  "subdir": ""
}
```

Installed plugins are validated, copied into `plugins/`, registered, and left disabled until enabled manually.

---

## Bundled starter plugins

The framework ships with these plugin folders:

| Plugin | Default | Purpose |
|---|---:|---|
| `dashboard_terminal` | enabled | Dashboard metadata and UI status |
| `log_viewer` | enabled | Log/event viewer API foundation |
| `system_monitor` | enabled | CPU/RAM/disk/temperature status |
| `memory_sqlite` | enabled | Memory DB status and starter memory API |
| `example_plugin` | disabled | Minimal example plugin |
| `face_pygame` | disabled | Stub for future HDMI face display |
| `emotion_engine` | disabled | Stub for future mood engine |

More plugins are planned in `roadmap.txt`.

---

## Logs and live console

Buddy logs to:

```text
logs/buddy.log
logs/buddy.error.log
```

The WebUI dashboard streams logs live over:

```text
/ws/console
```

The goal is ruthless observability: plugin loads, plugin failures, API errors, event chains, and system state changes should be visible without SSH spelunking.

---

## Error handling philosophy

BuddyCore must keep running when possible.

Plugin lifecycle calls, event handlers, background tasks, and API endpoints are guarded. A broken plugin should become a visible failed plugin, not a dead app.

Expected behavior:

```text
Plugin crashes → full traceback logged → plugin status updates → live console shows error → BuddyCore stays alive
```

---

## Development notes

Useful commands:

```bash
./scripts/run.sh
python -m compileall buddycore plugins
```

Reset runtime data:

```bash
rm -f data/buddy.db
rm -rf logs/*.log
```

Create a safe-mode flag:

```bash
touch config/safe_mode.flag
```

Remove it:

```bash
rm -f config/safe_mode.flag
```

Safe-mode behavior is partially scaffolded and will be expanded as the plugin system matures.

---

## License

Add your preferred license before publishing widely. MIT is a reasonable default for this kind of hobbyist framework.
