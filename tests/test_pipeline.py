from body.safety import check_safety
from brain.intent import parse_intent
from brain.planner import choose_action
from brain.state import RobotState


def test_known_command_mappings():
    cases = {
        "emergency stop": ("emergency_stop", "set_emergency_stop"),
        "clear emergency": ("clear_emergency_stop", "clear_emergency_stop"),
        "chirp": ("chirp", "play_chirp"),
        "look around": ("scan", "head_turn_left_right"),
        "act curious": ("curious", "express_curious"),
        "huh": ("confused", "express_confused"),
        "flutter": ("idle", "idle_flutter"),
        "wake": ("wake", "wake"),
        "sleep": ("sleep", "sleep"),
        "status": ("status", "report_status"),
        "walk forward": ("move", "step_forward"),
    }

    for command, expected in cases.items():
        intent = parse_intent(command)
        action = choose_action(intent)
        assert (intent, action) == expected


def test_shell_blocks_locomotion_and_allows_expression():
    state = RobotState()
    assert check_safety("play_chirp", state)[0] is True
    approved, reason = check_safety("step_forward", state)
    assert approved is False
    assert "blocked" in reason


def test_mobile_requires_movement_enabled_for_locomotion():
    state = RobotState(mode="mobile", movement_enabled=False)
    assert check_safety("step_forward", state)[0] is False

    state.movement_enabled = True
    state.sensors["front_clearance"] = 1.0
    assert check_safety("step_forward", state)[0] is True


def test_unknown_action_fails_closed():
    approved, reason = check_safety("raw_servo_angle_90", RobotState())
    assert approved is False
    assert "Unknown action" in reason


def test_emergency_stop_blocks_non_status_actions():
    state = RobotState(emergency_stop=True)
    assert check_safety("report_status", state)[0] is True
    approved, reason = check_safety("play_chirp", state)
    assert approved is False
    assert "Emergency stop active" in reason


def test_mobile_locomotion_requires_front_clearance_sensor():
    state = RobotState(mode="mobile", movement_enabled=True, sensors={"front_clearance": 0.2})
    approved, reason = check_safety("step_forward", state)
    assert approved is False
    assert "front_clearance" in reason

    state.sensors["front_clearance"] = 1.2
    assert check_safety("step_forward", state)[0] is True
