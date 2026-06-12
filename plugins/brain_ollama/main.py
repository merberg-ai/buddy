from buddycore.plugins.roadmap_plugin import RoadmapPlugin


class Plugin(RoadmapPlugin):
    plugin_kind = "brain_provider"
    readiness_note = "Configure Ollama base URL and model before routing prompts."


def setup(context):
    return Plugin(context)
