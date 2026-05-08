_INTENT_TO_ACTION = {
    "behavior_status":  "report_behavior_status",
    "behavior_tick":    "run_behavior_tick",
    "status":           "report_status",
    "camera_status":    "report_camera_status",
    "camera_diagnostics": "run_camera_diagnostics",
    "capture_image":    "capture_camera_frame",
    "distance_status":  "report_distance_status",
    "poll_distance":    "poll_distance_sensor",
    "scan":             "head_turn_left_right",
    "chirp":            "play_chirp",
    "sleep":            "sleep",
    "wake":             "wake",
    "curious":          "express_curious",
    "confused":         "express_confused",
    "move":             "step_forward",
    "idle":             "idle_flutter",
}


def choose_action(intent: str) -> str:
    return _INTENT_TO_ACTION.get(intent, "idle_flutter")
