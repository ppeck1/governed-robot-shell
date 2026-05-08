"""
Distance sensor backend.

Supported backends:
  mock  — returns a configured static value; safe for development/testing
  gpio  — HC-SR04 ultrasonic via RPi.GPIO (future, not implemented here)

This sensor is READ-ONLY. It never calls body or perception subsystems.

Classification thresholds (from config):
  distance > warning_distance_cm           → safe
  critical_distance_cm < distance <= warning → warning
  distance <= critical_distance_cm         → critical
"""

from datetime import datetime
from typing import Optional

_STATUS_SAFE     = "safe"
_STATUS_WARNING  = "warning"
_STATUS_CRITICAL = "critical"


class DistanceSensor:

    def __init__(self, config: dict) -> None:
        self.config               = config
        self.backend: str         = config.get("backend", "mock")
        self.mock_value: float    = float(config.get("mock_distance_cm", 100.0))
        self.warning_cm: float    = float(config.get("warning_distance_cm", 30.0))
        self.critical_cm: float   = float(config.get("critical_distance_cm", 15.0))
        self.timeout: float       = float(config.get("poll_timeout_seconds", 1.0))

        self.ready: bool                         = False
        self.last_distance_cm: Optional[float]   = None
        self.last_read_timestamp: Optional[str]  = None
        self.last_status: Optional[str]          = None

        self._init()

    # ── Init ─────────────────────────────────────────────────────────────────

    def _init(self) -> None:
        if self.backend == "mock":
            self.ready = True
            print(f"[DISTANCE SENSOR] Mock backend ready "
                  f"(simulated distance: {self.mock_value} cm)")
        elif self.backend == "gpio":
            print("[DISTANCE SENSOR] GPIO backend not yet implemented — "
                  "switch to 'mock' for now.")
        else:
            print(f"[DISTANCE SENSOR] Unknown backend '{self.backend}' — "
                  "falling back to mock.")
            self.backend  = "mock"
            self.ready    = True

    # ── Classification ────────────────────────────────────────────────────────

    def _classify(self, distance_cm: float) -> str:
        if distance_cm <= self.critical_cm:
            return _STATUS_CRITICAL
        if distance_cm <= self.warning_cm:
            return _STATUS_WARNING
        return _STATUS_SAFE

    # ── Polling ───────────────────────────────────────────────────────────────

    def poll_distance(self) -> Optional[float]:
        """
        Read distance. Returns cm value, or None if not ready.
        Updates last_distance_cm, last_read_timestamp, last_status.
        Never triggers body or perception actions.
        """
        if not self.ready:
            print("[DISTANCE SENSOR] Sensor not ready.")
            return None

        if self.backend == "mock":
            distance = self.mock_value
        else:
            print(f"[DISTANCE SENSOR] Backend '{self.backend}' not implemented.")
            return None

        ts = datetime.now().isoformat(timespec="seconds")
        classification = self._classify(distance)

        self.last_distance_cm    = distance
        self.last_read_timestamp = ts
        self.last_status         = classification

        print(f"\n[DISTANCE SENSOR]")
        print(f"  distance : {distance:.1f} cm")
        print(f"  status   : {classification}")

        return distance

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "enabled":              True,
            "backend":              self.backend,
            "ready":                self.ready,
            "last_distance_cm":     self.last_distance_cm,
            "last_read_timestamp":  self.last_read_timestamp,
            "last_status":          self.last_status,
            "warning_distance_cm":  self.warning_cm,
            "critical_distance_cm": self.critical_cm,
        }
