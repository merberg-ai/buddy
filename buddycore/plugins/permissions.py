LOW_RISK = {
    "events",
    "api",
    "webui",
    "face.control",
}

MEDIUM_RISK = {
    "config.read",
    "config.write",
    "memory.read",
    "memory.write",
    "voice.speak",
    "network",
    "brain.call",
}

HIGH_RISK = {
    "voice.listen",
    "vision.camera",
    "vision.read",
    "person.recognition",
    "motion.control",
    "filesystem.write",
}

DANGER_RISK = {
    "shell",
    "motion.calibrate",
}


def permission_risk(permission: str) -> str:
    if permission in DANGER_RISK:
        return "danger"
    if permission in HIGH_RISK:
        return "high"
    if permission in MEDIUM_RISK:
        return "medium"
    if permission in LOW_RISK:
        return "low"
    return "unknown"
