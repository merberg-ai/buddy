from buddycore.plugins.roadmap_plugin import RoadmapPlugin


class Plugin(RoadmapPlugin):
    plugin_kind = "brain_provider"
    readiness_note = "Set OPENAI_API_KEY and choose a model before routing prompts."


def setup(context):
    return Plugin(context)
