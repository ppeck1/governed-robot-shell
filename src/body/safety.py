from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from body.audio_cues import cue_for_blocked
from brain.action_registry import get_action

if TYPE_CHECKING:
    from brain.state import RobotState

CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "safety.json"

_DEFAULT_CONFIG = {
    "blocked_actions": ["step_forward"],
    "sensor_thresholds": {"min_front_clearance": 0.5},
    "allowed_modes": {
        "shell": [
            "play_chirp",
            "head_turn_left_right",
            "enter_idle_mode",
            "idle_flutter",
            "express_curious",
            "express_confused",
            "wake",
            "sleep",
            "report_status",
            "set_emergency_stop",
            "clear_emergency_stop",
        ]
    },
}

_EMERGENCY_ALLOWED = {"report_status", "sleep", "clear_emergency_stop"}


@dataclass(frozen=True)
class SafetyResult:
    gate_id: str
    action: str
    decision: str
    reason: str
    mode: str
    movement_enabled: bool
    emergency_stop: bool
    motion_inhibited: bool
    sensor_snapshot: dict
    action_category: str
    selected_cue: str

    @property
    def approved(self) -> bool:
        return self.decision == "approved"

    def as_dict(self) -> dict:
        data = asdict(self)
        data["approved"] = self.approved
        return data


def _load_config() -> dict:
    try:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return _DEFAULT_CONFIG


def evaluate_safety(action: str, state: Optional["RobotState"] = None) -> SafetyResult:
    config = _load_config()
    blocked = set(config.get("blocked_actions", []))
    thresholds = config.get("sensor_thresholds", {})
    min_front_clearance = float(thresholds.get("min_front_clearance", 0.5))

    mode = getattr(state, "mode", "shell") if state else "shell"
    movement_enabled = getattr(state, "movement_enabled", False) if state else False
    emergency_stop = getattr(state, "emergency_stop", False) if state else False
    motion_inhibited = getattr(state, "motion_inhibited", False) if state else False
    sensors = dict(getattr(state, "sensors", {}) or {})

    spec = get_action(action)

    if spec is None:
        return _result(action, "blocked", f"Unknown action '{action}'. Failing closed.", mode, movement_enabled, emergency_stop, motion_inhibited, sensors, "unknown", cue_for_blocked(unknown_action=True))

    if emergency_stop and not spec.allowed_during_emergency:
        return _result(action, "blocked", f"Emergency stop active. '{action}' is blocked.", mode, movement_enabled, emergency_stop, motion_inhibited, sensors, spec.category, cue_for_blocked())

    if spec.category == "movement" or action in blocked or spec.blocked_by_default:
        if mode not in spec.allowed_modes or (spec.requires_movement_enabled and not movement_enabled):
            return _result(action, "blocked", f"'{action}' is blocked. Mode={mode}, movement_enabled={movement_enabled}.", mode, movement_enabled, emergency_stop, motion_inhibited, sensors, spec.category, cue_for_blocked())
        if motion_inhibited:
            return _result(action, "blocked", f"'{action}' is blocked by motion_inhibited.", mode, movement_enabled, emergency_stop, motion_inhibited, sensors, spec.category, cue_for_blocked())
        if spec.requires_front_clearance:
            front_clearance = sensors.get("front_clearance")
            if front_clearance is None:
                return _result(action, "blocked", f"'{action}' is blocked: front_clearance sensor missing.", mode, movement_enabled, emergency_stop, motion_inhibited, sensors, spec.category, cue_for_blocked())
            if float(front_clearance) < min_front_clearance:
                return _result(action, "blocked", f"'{action}' is blocked: front_clearance={front_clearance} below {min_front_clearance}.", mode, movement_enabled, emergency_stop, motion_inhibited, sensors, spec.category, cue_for_blocked())
        return _result(action, "approved", "Locomotion approved by state and sensor gates.", mode, movement_enabled, emergency_stop, motion_inhibited, sensors, spec.category, spec.default_cue)

    if mode not in spec.allowed_modes:
        return _result(action, "blocked", f"'{action}' not allowed in mode '{mode}'.", mode, movement_enabled, emergency_stop, motion_inhibited, sensors, spec.category, cue_for_blocked())

    return _result(action, "approved", "Action approved.", mode, movement_enabled, emergency_stop, motion_inhibited, sensors, spec.category, spec.default_cue)


def check_safety(action: str, state: Optional["RobotState"] = None):
    result = evaluate_safety(action, state)
    return result.approved, result.reason


def _result(
    action: str,
    decision: str,
    reason: str,
    mode: str,
    movement_enabled: bool,
    emergency_stop: bool,
    motion_inhibited: bool,
    sensors: dict,
    action_category: str,
    selected_cue: str,
) -> SafetyResult:
    return SafetyResult(
        gate_id="robot_safety_gate.v0.2",
        action=action,
        decision=decision,
        reason=reason,
        mode=mode,
        movement_enabled=movement_enabled,
        emergency_stop=emergency_stop,
        motion_inhibited=motion_inhibited,
        sensor_snapshot=dict(sensors),
        action_category=action_category,
        selected_cue=selected_cue,
    )
