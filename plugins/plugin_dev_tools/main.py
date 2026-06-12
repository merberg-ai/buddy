from buddycore.plugins.roadmap_plugin import RoadmapPlugin


class Plugin(RoadmapPlugin):
    plugin_kind = "developer_tools"
    readiness_note = "Enable scaffold writes explicitly before generating plugin files."


def setup(context):
    return Plugin(context)
