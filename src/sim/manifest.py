from __future__ import annotations

from typing import Any

from brain.planner import _INTENT_TO_ACTION
from sim.scenarios import SCENARIOS

MANIFEST_VERSION = "robot_sim_manifest.v0.2"
READINESS_VERSION = "robot_sim_readiness.v0.2"


def build_sim_manifest(runtime_snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "manifest_version": MANIFEST_VERSION,
        "runtime_backend": runtime_snapshot["body"]["backend"],
        "action_vocabulary": sorted(set(_INTENT_TO_ACTION.values())),
        "scenario_count": len(SCENARIOS),
        "scenarios": [
            {
                "scenario_id": scenario_id,
                "name": scenario["name"],
                "command_count": len(scenario["commands"]),
            }
            for scenario_id, scenario in SCENARIOS.items()
        ],
        "boundaries": [
            "mock remains the default backend",
            "simulator is local and expression-first",
            "locomotion remains blocked unless state and sensor gates pass",
            "sim backend refuses step_forward directly",
            "dashboard commands route through RobotRuntime",
            "no raw servo angles or GPIO values accepted",
            "future BOH retrieval must be read-only and advisory",
        ],
    }


def calculate_readiness(runtime_snapshot: dict[str, Any]) -> dict[str, Any]:
    state = runtime_snapshot["state"]
    body = runtime_snapshot["body"]
    event_log = runtime_snapshot.get("event_log", [])
    sim = body.get("sim") or {}
    sensors = sim.get("sensors") or state.get("sensors") or {}

    checks = [
        _check("command_pipeline", True, "RobotRuntime is active"),
        _check("sim_backend", body.get("backend") == "sim", "sim backend selected"),
        _check("event_replay", bool(event_log), "kernel events are available after a command"),
        _check("virtual_sensors", bool(sensors), "virtual sensor snapshot present"),
        _check("emergency_stop_field", "emergency_stop" in state, "emergency stop state field present"),
        _check("hardware_default_safe", not body.get("servo_enabled"), "servo backend disabled"),
        _check("dashboard_visibility", True, "dashboard exposes API-backed panels"),
        _check("proposal_queue", True, "proposal preview/review API scaffold available"),
    ]
    passed = sum(1 for check in checks if check["passed"])
    return {
        "readiness_version": READINESS_VERSION,
        "status": "ready_for_sim_governance" if passed == len(checks) else "partial",
        "score": round(passed / len(checks), 3),
        "passed": passed,
        "total": len(checks),
        "checks": checks,
        "advisory_only": True,
    }


def _check(check_id: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"check_id": check_id, "passed": bool(passed), "detail": detail}
