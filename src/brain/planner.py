_INTENT_TO_ACTION = {
    "emergency_stop": "set_emergency_stop",
    "clear_emergency_stop": "clear_emergency_stop",
    "status":  "report_status",
    "scan":    "head_turn_left_right",
    "chirp":   "play_chirp",
    "sleep":   "sleep",
    "wake":    "wake",
    "curious": "express_curious",
    "confused":"express_confused",
    "move":    "step_forward",
    "idle":    "idle_flutter",
}


def choose_action(intent: str) -> str:
    return _INTENT_TO_ACTION.get(intent, "idle_flutter")
