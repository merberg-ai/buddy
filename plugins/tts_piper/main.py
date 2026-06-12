from buddycore.plugins.roadmap_plugin import RoadmapPlugin


class Plugin(RoadmapPlugin):
    plugin_kind = "text_to_speech"
    readiness_note = "Configure Piper executable, voice model, and audio output before speaking."


def setup(context):
    return Plugin(context)
