from runtime import RobotRuntime
from sim.scenarios import new_sim_runtime, run_scenario


def test_sim_backend_updates_expression_only_after_approved_action():
    runtime = new_sim_runtime()
    event = runtime.process_command("act curious", source="test")
    snapshot = runtime.snapshot()

    assert event["approved"] is True
    assert snapshot["body"]["backend"] == "sim"
    assert snapshot["body"]["sim"]["robot"]["expression"] == "curious"
    assert snapshot["body"]["sim"]["robot"]["pose"] == {
        "x": 0.0,
        "z": 0.0,
        "heading_degrees": 0.0,
    }


def test_blocked_walk_does_not_change_sim_pose():
    runtime = new_sim_runtime()
    event = runtime.process_command("walk forward", source="test")
    pose = runtime.snapshot()["body"]["sim"]["robot"]["pose"]

    assert event["approved"] is False
    assert pose["x"] == 0.0
    assert pose["z"] == 0.0


def test_scenario_replay_is_deterministic():
    first = run_scenario("curious_confused")
    second = run_scenario("curious_confused")

    assert first["passed"] is True
    assert second["passed"] is True
    assert first["final_snapshot"]["state"] == second["final_snapshot"]["state"]
    assert first["final_snapshot"]["body"]["sim"] == second["final_snapshot"]["body"]["sim"]


def test_runtime_writes_kernel_events_and_replays_final_state():
    runtime = new_sim_runtime()
    runtime.process_command("chirp", source="test")
    exported = runtime.export()
    event_types = [event["event_type"] for event in exported["event_log"]]

    assert "command_received" in event_types
    assert "safety_gate_evaluated" in event_types
    assert "body_action_applied" in event_types

    replayed = runtime.replay(exported["event_log"])
    assert replayed["final_state"]["last_action"] == "play_chirp"


def test_emergency_stop_is_finite_governed_action():
    runtime = new_sim_runtime()
    stop = runtime.process_command("emergency stop", source="test")
    blocked = runtime.process_command("chirp", source="test")
    clear = runtime.process_command("clear emergency", source="test")

    assert stop["approved"] is True
    assert blocked["approved"] is False
    assert clear["approved"] is True
    assert runtime.snapshot()["state"]["emergency_stop"] is False


def test_mock_remains_default_backend():
    runtime = RobotRuntime()
    assert runtime.snapshot()["body"]["backend"] == "mock"
