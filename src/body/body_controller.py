"""
Session-scoped body backend controller.

Instantiated once at startup. Selects and initializes the correct
backend based on config/body.json. All action routing for the
session goes through the single instance.

Routing:
  backend = "mock"                          → mock body
  backend = "servo", servo.enabled = True   → ServoBody (one instance)
  backend = "servo", servo.enabled = False  → mock body + one-time warning
  backend = unknown                         → mock body + one-time warning
  config missing / malformed                → mock body + one-time warning
"""

import json
from pathlib import Path
from typing import Optional

PROJECT_ROOT     = Path(__file__).resolve().parents[2]
BODY_CONFIG_PATH = PROJECT_ROOT / "config" / "body.json"

_DEFAULT_CONFIG = {"backend": "mock", "servo": {"enabled": False}}


def _load_config() -> dict:
    try:
        return json.loads(BODY_CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        print("[BODY CONTROLLER] config/body.json missing or malformed — using mock.")
        return _DEFAULT_CONFIG


class BodyController:

    def __init__(self) -> None:
        config     = _load_config()
        backend    = config.get("backend", "mock")
        servo_cfg  = config.get("servo", {})
        motion_cfg = config.get("motion", {})
        servo_on   = servo_cfg.get("enabled", False)

        self._servo_body  = None
        self._backend_name = "mock"

        if backend == "servo":
            if servo_on:
                from body.servo_body import ServoBody
                self._servo_body   = ServoBody(servo_cfg, motion_cfg)
                self._backend_name = "servo"
                print("[BODY CONTROLLER] Backend: servo (opt-in)")
            else:
                print("[BODY CONTROLLER] Servo backend requested but servo.enabled "
                      "is false — falling back to mock.")
                print("[BODY CONTROLLER] Backend: mock")
        elif backend == "mock":
            print("[BODY CONTROLLER] Backend: mock")
        else:
            print(f"[BODY CONTROLLER] Unknown backend '{backend}' — using mock.")
            print("[BODY CONTROLLER] Backend: mock")

    # ── Action routing ────────────────────────────────────────────────────────

    def execute_action(self, action: str) -> None:
        if self._servo_body is not None:
            self._servo_body.execute_action(action)
        else:
            from body.mock_body import execute_action as mock_exec
            mock_exec(action)

    # ── Observability ─────────────────────────────────────────────────────────

    def get_servo_positions(self) -> Optional[dict]:
        if self._servo_body is not None:
            return self._servo_body.get_positions()
        return None

    def get_status(self) -> dict:
        servo_body   = self._servo_body
        servo_ready  = servo_body is not None and not servo_body.dry_run
        positions    = servo_body.get_positions() if servo_body else {}

        return {
            "backend":         self._backend_name,
            "servo_enabled":   servo_body is not None,
            "servo_ready":     servo_ready,
            "servo_positions": positions,
        }
