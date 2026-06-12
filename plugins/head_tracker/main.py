from buddycore.plugins.roadmap_plugin import RoadmapPlugin


class Plugin(RoadmapPlugin):
    plugin_kind = "head_tracker"
    readiness_note = "Configure vision and motion plugins before tracking."


def setup(context):
    return Plugin(context)
