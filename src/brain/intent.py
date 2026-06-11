def parse_intent(user_input: str) -> str:
    text = user_input.lower()

    if any(w in text for w in ("clear emergency", "clear stop", "resume safety")):
        return "clear_emergency_stop"

    if any(w in text for w in ("emergency stop", "e-stop", "estop", "hard stop")):
        return "emergency_stop"

    if any(w in text for w in ("status", "state", "diagnostic", "diagnostics",
                                "what are you doing")):
        return "status"

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
