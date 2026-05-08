"""
Session-scoped sensor controller.

Instantiated once at startup alongside RobotState, BodyController,
and PerceptionController. Owns all sensor backends for the runtime.

Accepts an optional RobotState reference so sensor polls can write
directly into state.sensors — the first environmental data channel
into the robot's runtime state.
"""

import json
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from brain.state import RobotState

PROJECT_ROOT      = Path(__file__).resolve().parents[2]
BODY_CONFIG_PATH  = PROJECT_ROOT / "config" / "body.json"

_DEFAULT_DISTANCE_CONFIG = {
    "enabled":              False,
    "backend":              "mock",
    "trigger_pin":          None,
    "echo_pin":             None,
    "mock_distance_cm":     100.0,
    "warning_distance_cm":  30.0,
    "critical_distance_cm": 15.0,
    "poll_timeout_seconds": 1.0,
}


def _load_distance_config() -> dict:
    try:
        cfg = json.loads(BODY_CONFIG_PATH.read_text(encoding="utf-8"))
        return cfg.get("distance_sensor", _DEFAULT_DISTANCE_CONFIG)
    except (FileNotFoundError, json.JSONDecodeError):
        return _DEFAULT_DISTANCE_CONFIG


class SensorController:

    def __init__(self, state: Optional["RobotState"] = None) -> None:
        self._state   = state
        dist_cfg      = _load_distance_config()
        self._enabled = dist_cfg.get("enabled", False)
        self._sensor  = None

        if self._enabled:
            from sensors.distance_sensor import DistanceSensor
            self._sensor = DistanceSensor(dist_cfg)
        else:
            print("[SENSORS] Distance sensor disabled.")

    # ── Polling ───────────────────────────────────────────────────────────────

    def poll_distance(self) -> Optional[float]:
        """Poll distance sensor and write result into state.sensors."""
        if not self._enabled:
            print("[SENSORS] Distance sensor is disabled in config.")
            return None
        if self._sensor is None:
            print("[SENSORS] No distance sensor backend available.")
            return None

        value = self._sensor.poll_distance()

        if value is not None and self._state is not None:
            self._state.sensors["distance_cm"]        = value
            self._state.sensors["distance_status"]    = self._sensor.last_status
            self._state.sensors["distance_timestamp"] = self._sensor.last_read_timestamp

        return value

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        if self._sensor is not None:
            return self._sensor.get_status()
        return {
            "enabled":              self._enabled,
            "backend":              "none",
            "ready":                False,
            "last_distance_cm":     None,
            "last_read_timestamp":  None,
            "last_status":          None,
            "warning_distance_cm":  None,
            "critical_distance_cm": None,
        }
