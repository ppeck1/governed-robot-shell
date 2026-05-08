_MOCK_BEHAVIORS = {
    "play_chirp":           "chirp chirp",
    "head_turn_left_right": "head scans left... and right",
    "idle_flutter":         "small idle flutter",
    "express_curious":      "curious head tilt and soft chirp",
    "express_confused":     "confused twitch",
    "wake":                 "waking posture — servos rising",
    "sleep":                "settling into sleep mode",
    "enter_idle_mode":      "entering low-power idle",
    "step_forward":         "would step forward (mock only)",
}


def execute_action(action: str) -> None:
    description = _MOCK_BEHAVIORS.get(action, f"unknown action: {action}")
    print(f"\n[MOCK BODY] {description}")
