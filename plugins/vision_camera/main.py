from buddycore.plugins.roadmap_plugin import RoadmapPlugin


class Plugin(RoadmapPlugin):
    plugin_kind = "vision_camera"
    readiness_note = "Configure camera hardware before preview or capture."


def setup(context):
    return Plugin(context)
