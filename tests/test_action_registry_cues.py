from body.audio_cues import CUE_VOCABULARY
from body.safety import evaluate_safety
from brain.action_registry import ACTION_REGISTRY, get_action
from brain.planner import _INTENT_TO_ACTION
from brain.state import RobotState
from runtime import CommandEnvelope
from sim.scenarios import new_sim_runtime


def test_every_planner_action_is_registered():
    for action in _INTENT_TO_ACTION.values():
        assert action in ACTION_REGISTRY


def test_registry_entries_have_required_metadata():
    for action_id, spec in ACTION_REGISTRY.items():
        assert spec.action_id == action_id
        assert spec.category
        assert spec.allowed_modes
        assert spec.backend_support
        assert isinstance(spec.allowed_during_emergency, bool)
        assert spec.default_cue in CUE_VOCABULARY


def test_step_forward_registry_marks_movement_blocked_default():
    spec = get_action("step_forward")
    assert spec is not None
    assert spec.category == "movement"
    assert spec.blocked_by_default is True
    assert spec.requires_movement_enabled is True
    assert spec.requires_front_clearance is True


def test_unknown_action_selects_confused_cue():
    result = evaluate_safety("raw_servo_angle_90", RobotState())
    assert result.approved is False
    assert result.selected_cue == "chirp_confused"


def test_blocked_walk_selects_blocked_cue():
    runtime = new_sim_runtime()
    event = runtime.process_command("walk forward", source="test")
    robot = runtime.snapshot()["body"]["sim"]["robot"]

    assert event["approved"] is False
    assert event["selected_cue"] == "chirp_blocked"
    assert robot["latest_audio_cue"] == "chirp_blocked"
    assert robot["cue_count"] == 1


def test_expression_commands_select_specific_cues():
    runtime = new_sim_runtime()
    curious = runtime.process_command("act curious", source="test")
    sleep = runtime.process_command("sleep", source="test")
    wake = runtime.process_command("wake", source="test")

    assert curious["selected_cue"] == "chirp_curious"
    assert sleep["selected_cue"] == "chirp_sleepy"
    assert wake["selected_cue"] == "chirp_wake"
    assert runtime.snapshot()["body"]["sim"]["robot"]["latest_audio_cue"] == "chirp_wake"


def test_emergency_stop_selects_alert_and_blocks_expression():
    runtime = new_sim_runtime()
    stop = runtime.process_command("emergency stop", source="test")
    blocked = runtime.process_command("act curious", source="test")

    assert stop["selected_cue"] == "chirp_alert"
    assert blocked["approved"] is False
    assert blocked["selected_cue"] == "chirp_blocked"


def test_command_envelope_preview_does_not_execute_body_action():
    runtime = new_sim_runtime()
    event = runtime.process_command(
        CommandEnvelope(raw_input="act curious", source="test", execution_mode="preview")
    )
    snapshot = runtime.snapshot()

    assert event["approved"] is True
    assert event["body_result"] == {"preview_only": True}
    assert snapshot["state"]["last_action"] is None
    assert snapshot["body"]["sim"]["robot"]["expression"] == "neutral"
    assert snapshot["body"]["sim"]["robot"]["cue_count"] == 0


def test_nonverbal_cue_vocabulary_has_no_speech_text():
    for cue in CUE_VOCABULARY:
        assert cue.startswith("chirp_")
        assert "speak" not in cue
        assert "tts" not in cue
