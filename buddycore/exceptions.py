class BuddyError(Exception):
    """Base class for Buddy-specific errors."""


class PluginLoadError(BuddyError):
    pass


class PluginDependencyError(BuddyError):
    pass


class PluginPermissionError(BuddyError):
    pass


class PluginConfigError(BuddyError):
    pass


class DeviceUnavailableError(BuddyError):
    pass


class BrainProviderError(BuddyError):
    pass


class MotionSafetyError(BuddyError):
    pass
