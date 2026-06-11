from __future__ import annotations

from copy import deepcopy
from typing import Any

from runtime import RobotRuntime


SIM_BODY_CONFIG = {
    "backend": "sim",
    "sim": {
        "world": {
            "width": 8.0,
            "depth": 8.0,
        }
    },
}


SCENARIOS: dict[str, dict[str, Any]] = {
    "boot_status": {
        "name": "Boot and status",
        "commands": ["status"],
        "expected": {"last_action": "report_status", "approved_count": 1},
    },
    "chirp": {
        "name": "Chirp expression",
        "commands": ["chirp"],
        "expected": {"last_action": "play_chirp", "expression": "bright"},
    },
    "scan": {
        "name": "Look around",
        "commands": ["look around"],
        "expected": {"last_action": "head_turn_left_right", "expression": "scanning"},
    },
    "curious_confused": {
        "name": "Curious then confused",
        "commands": ["act curious", "huh"],
        "expected": {"last_action": "express_confused", "expression": "confused"},
    },
    "sleep_wake": {
        "name": "Sleep then wake",
        "commands": ["sleep", "wake"],
        "expected": {"last_action": "wake", "power_state": "awake"},
    },
    "blocked_walk": {
        "name": "Walk forward blocked in shell mode",
        "commands": ["walk forward"],
        "expected": {"last_action": None, "approved_count": 0, "pose_x": 0.0, "pose_z": 0.0},
    },
    "obstacle_probe": {
        "name": "Obstacle-proximity sensor probe",
        "commands": ["look around", "status"],
        "expected": {"front_clearance_max": 8.0},
    },
}


def new_sim_runtime() -> RobotRuntime:
    return RobotRuntime(body_config=deepcopy(SIM_BODY_CONFIG))


def run_scenario(scenario_id: str) -> dict[str, Any]:
    scenario = SCENARIOS[scenario_id]
    runtime = new_sim_runtime()
    runtime.event_writer.write(
        "scenario_started",
        source=f"scenario:{scenario_id}",
        payload={"scenario_id": scenario_id, "name": scenario["name"]},
        state_before=runtime.state.snapshot(),
    )
    events = [runtime.process_command(command, source=f"scenario:{scenario_id}") for command in scenario["commands"]]
    snapshot = runtime.snapshot()
    failures = _evaluate(snapshot, events, scenario.get("expected", {}))
    runtime.event_writer.write(
        "scenario_completed",
        source=f"scenario:{scenario_id}",
        payload={"scenario_id": scenario_id, "passed": not failures, "failures": failures},
        state_after=runtime.state.snapshot(),
    )
    snapshot = runtime.snapshot()
    return {
        "scenario_id": scenario_id,
        "name": scenario["name"],
        "commands": list(scenario["commands"]),
        "passed": not failures,
        "failures": failures,
        "final_snapshot": snapshot,
    }


def run_all_scenarios() -> list[dict[str, Any]]:
    return [run_scenario(scenario_id) for scenario_id in SCENARIOS]


def list_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": scenario_id,
            "name": scenario["name"],
            "commands": list(scenario["commands"]),
        }
        for scenario_id, scenario in SCENARIOS.items()
    ]


def _evaluate(snapshot: dict[str, Any], events: list[dict[str, Any]], expected: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    sim = snapshot["body"].get("sim", {})
    robot = sim.get("robot", {})
    pose = robot.get("pose", {})
    sensors = sim.get("sensors", {})
    approved_count = sum(1 for event in events if event["approved"])

    if "last_action" in expected and snapshot["state"].get("last_action") != expected["last_action"]:
        failures.append(f"last_action expected {expected['last_action']!r}")
    if "approved_count" in expected and approved_count != expected["approved_count"]:
        failures.append(f"approved_count expected {expected['approved_count']}")
    if "expression" in expected and robot.get("expression") != expected["expression"]:
        failures.append(f"expression expected {expected['expression']!r}")
    if "power_state" in expected and robot.get("power_state") != expected["power_state"]:
        failures.append(f"power_state expected {expected['power_state']!r}")
    if "pose_x" in expected and pose.get("x") != expected["pose_x"]:
        failures.append(f"pose.x expected {expected['pose_x']}")
    if "pose_z" in expected and pose.get("z") != expected["pose_z"]:
        failures.append(f"pose.z expected {expected['pose_z']}")
    if "front_clearance_max" in expected and sensors.get("front_clearance", 0) > expected["front_clearance_max"]:
        failures.append(f"front_clearance above {expected['front_clearance_max']}")

    return failures
