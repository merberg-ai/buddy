from buddycore.plugins.roadmap_plugin import RoadmapPlugin


class Plugin(RoadmapPlugin):
    plugin_kind = "vision_detector"
    readiness_note = "Install a YOLO runtime and configure camera input before detection."


def setup(context):
    return Plugin(context)
