import shutil
import psutil
from buddycore.plugins import BuddyPlugin


class Plugin(BuddyPlugin):
    async def on_load(self):
        self.context.api.add_route("GET", "/status", self.status)

    async def on_enable(self):
        await self.context.log_console("INFO", "System Monitor plugin online")

    async def status(self, request):
        disk = shutil.disk_usage("/")
        temp = None
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                first = next(iter(temps.values()))
                if first:
                    temp = first[0].current
        except Exception:
            temp = None
        return {
            "ok": True,
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "ram_percent": psutil.virtual_memory().percent,
            "disk_percent": round((disk.used / disk.total) * 100, 2),
            "temperature_c": temp,
            "boot_time": psutil.boot_time(),
        }


def setup(context):
    return Plugin(context)
