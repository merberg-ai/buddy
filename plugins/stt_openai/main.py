from buddycore.plugins.roadmap_plugin import RoadmapPlugin


class Plugin(RoadmapPlugin):
    plugin_kind = "speech_to_text"
    readiness_note = "Set OPENAI_API_KEY and choose a transcription model before use."


def setup(context):
    return Plugin(context)
