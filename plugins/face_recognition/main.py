from buddycore.plugins.roadmap_plugin import RoadmapPlugin


class Plugin(RoadmapPlugin):
    plugin_kind = "face_recognition"
    readiness_note = "Configure camera input and explicit enrollment confirmation before recognition."


def setup(context):
    return Plugin(context)
