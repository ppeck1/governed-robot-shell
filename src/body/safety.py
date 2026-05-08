"""
Safety layer.

Evaluation order for any requested action:
  1. Unknown action / mode allowlist check  → fail closed on unknown
  2. Explicit blocked_actions list          → always blocked
  3. Movement gate: mode + movement_enabled → blocked unless mobile + enabled
  4. Sensor gates: environment constraints  → block if critical distance etc.
  5. Approve

Public API (unchanged):
  check_safety(action, state=None) -> tuple[bool, str]

Helpers (testable independently):
  is_movement_action(action, config) -> bool
  check_sensor_gates(action, state, config) -> tuple[bool, str]
"""

import json
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from brain.state import RobotState

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "safety.json"

_DEFAULT_CONFIG = {
    "blocked_actions": ["step_forward"],
    "allowed_modes": {
        "shell": [
            "play_chirp", "head_turn_left_right", "enter_idle_mode",
            "idle_flutter", "express_curious", "express_confused",
            "wake", "sleep",
        ]
    },
    "movement_actions": ["step_forward"],
    "sensor_gates": {
        "distance": {
            "enabled": True,
            "blocked_statuses": ["critical"],
            "unknown_blocks_movement": False,
        }
    },
}


def _load_config() -> dict:
    try:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return _DEFAULT_CONFIG


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_movement_action(action: str, config: dict) -> bool:
    """Return True if action is classified as a movement-class action."""
    return action in config.get("movement_actions", [])


def check_sensor_gates(action: str, state: Optional["RobotState"],
                       config: dict) -> tuple:
    """
    Evaluate sensor gates for a movement-class action.

    Returns (approved: bool, reason: str).
    Called only after action is confirmed to be a movement action.
    If state is None, sensor gates are skipped (no state → no sensor data).
    """
    if state is None:
        return True, "Action approved."

    gates = config.get("sensor_gates", {})
    distance_gate = gates.get("distance", {})

    if not distance_gate.get("enabled", False):
        return True, "Action approved."

    blocked_statuses         = set(distance_gate.get("blocked_statuses", []))
    unknown_blocks_movement  = distance_gate.get("unknown_blocks_movement", False)
    distance_status          = state.sensors.get("distance_status")

    if distance_status is None:
        if unknown_blocks_movement:
            return False, ("Movement blocked: distance sensor status unknown "
                           "and unknown_blocks_movement is true.")
        return True, "Action approved."

    if distance_status in blocked_statuses:
        dist_cm = state.sensors.get("distance_cm", "?")
        return False, (f"Movement blocked by sensor gate: "
                       f"distance_status='{distance_status}' "
                       f"({dist_cm} cm).")

    return True, "Action approved."


# ── Public gate ───────────────────────────────────────────────────────────────

def check_safety(action: str, state: Optional["RobotState"] = None) -> tuple:
    """
    Evaluate whether an action may execute.

    Returns (approved: bool, reason: str).
    """
    config = _load_config()

    blocked      = set(config.get("blocked_actions", []))
    allowed_modes = config.get("allowed_modes", {})

    mode             = getattr(state, "mode",             "shell") if state else "shell"
    movement_enabled = getattr(state, "movement_enabled", False)   if state else False

    # 1. Build known action set; unknown → fail closed
    all_known: set = set()
    for actions in allowed_modes.values():
        all_known.update(actions)
    all_known.update(blocked)
    all_known.update(config.get("movement_actions", []))

    if action not in all_known:
        return False, f"Unknown action '{action}'. Failing closed."

    # 2. Explicit blocked list
    if action in blocked:
        # 3. Movement gate — only escape is mobile mode + movement_enabled
        if mode == "mobile" and movement_enabled:
            pass    # falls through to sensor gate below
        else:
            return False, (f"'{action}' is blocked. "
                           f"Mode={mode}, movement_enabled={movement_enabled}.")

    # 3b. Mode allowlist (for non-blocked actions)
    elif action not in allowed_modes.get(mode, []):
        return False, f"'{action}' not allowed in mode '{mode}'."

    # 4. Sensor gates (movement-class actions only)
    if is_movement_action(action, config):
        approved, reason = check_sensor_gates(action, state, config)
        if not approved:
            return False, reason

    return True, "Action approved."
