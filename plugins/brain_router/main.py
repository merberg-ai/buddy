from buddycore.plugins.roadmap_plugin import RoadmapPlugin


class Plugin(RoadmapPlugin):
    plugin_kind = "brain_router"
    readiness_note = "Configure primary and fallback brain providers before routing prompts."


def setup(context):
    return Plugin(context)
