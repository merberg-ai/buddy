from buddycore.plugins.roadmap_plugin import RoadmapPlugin


class Plugin(RoadmapPlugin):
    plugin_kind = "motion_control"
    readiness_note = "Calibrate channels, verify hard limits, and arm manually before motion."


def setup(context):
    return Plugin(context)
