from buddycore.plugins.roadmap_plugin import RoadmapPlugin


class Plugin(RoadmapPlugin):
    plugin_kind = "voice_pipeline"
    readiness_note = "Enable and configure wake word, STT, brain, and TTS plugins before live voice use."


def setup(context):
    return Plugin(context)
