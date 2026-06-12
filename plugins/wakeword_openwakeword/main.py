from buddycore.plugins.roadmap_plugin import RoadmapPlugin


class Plugin(RoadmapPlugin):
    plugin_kind = "wake_word"
    readiness_note = "Configure microphone device, threshold, and OpenWakeWord model before enabling live detection."


def setup(context):
    return Plugin(context)
