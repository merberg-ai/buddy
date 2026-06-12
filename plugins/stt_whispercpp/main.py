from buddycore.plugins.roadmap_plugin import RoadmapPlugin


class Plugin(RoadmapPlugin):
    plugin_kind = "speech_to_text"
    readiness_note = "Configure whisper.cpp executable and model path before transcription."


def setup(context):
    return Plugin(context)
