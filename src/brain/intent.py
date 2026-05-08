def parse_intent(user_input: str) -> str:
    text = user_input.lower()

    # Behavior scheduler commands
    if any(w in text for w in ("behavior status", "scheduler status", "idle status")):
        return "behavior_status"
    if any(w in text for w in ("behavior tick", "scheduler tick",
                                "idle tick", "test behavior")):
        return "behavior_tick"

    # Camera diagnostics before generic status
    if any(w in text for w in ("camera diagnostic", "diagnose camera",
                                "check webcam", "probe camera", "probe cameras",
                                "list cameras")):
        return "camera_diagnostics"
    if any(w in text for w in ("camera", "webcam")) and \
       any(w in text for w in ("diagnostic", "diagnostics")):
        return "camera_diagnostics"

    # Distance sensor
    if any(w in text for w in ("poll distance", "measure distance",
                                "scan distance", "read sensor")):
        return "poll_distance"
    if any(w in text for w in ("distance status", "sensor status",
                                "check distance", "how far")):
        return "distance_status"
    if text in ("distance", "sensor", "range"):
        return "distance_status"

    # General status (after sensor-specific checks)
    if any(w in text for w in ("status", "state", "diagnostic", "diagnostics",
                                "what are you doing")):
        return "status"

    if any(w in text for w in ("camera status", "check camera", "webcam")):
        return "camera_status"

    if any(w in text for w in ("capture image", "take picture", "take photo",
                                "look with camera", "capture frame")):
        return "capture_image"

    if any(w in text for w in ("look", "scan", "around")):
        return "scan"

    if any(w in text for w in ("chirp", "beep", "sound")):
        return "chirp"

    if any(w in text for w in ("sleep", "rest")):
        return "sleep"

    if any(w in text for w in ("wake", "awake")):
        return "wake"

    if any(w in text for w in ("curious", "investigate", "what is that")):
        return "curious"

    if any(w in text for w in ("confused", "unsure", "huh")):
        return "confused"

    if any(w in text for w in ("flutter", "idle", "wiggle")):
        return "idle"

    if any(w in text for w in ("walk", "move", "forward", "come here")):
        return "move"

    return "idle"
