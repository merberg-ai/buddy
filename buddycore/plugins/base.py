from __future__ import annotations


class BuddyPlugin:
    """Base class for Buddy plugins.

    Plugins may subclass this, but only a setup(context) function is required.
    """

    def __init__(self, context):
        self.context = context
        self.config = context.config
        self.logger = context.logger

    async def on_load(self):
        pass

    async def on_enable(self):
        pass

    async def on_disable(self):
        pass

    async def on_unload(self):
        pass

    async def on_config_updated(self, config):
        self.config = config
