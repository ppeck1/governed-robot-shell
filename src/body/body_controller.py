"""
Session-scoped body backend controller.

The controller is instantiated once at startup. It selects mock, sim, or servo
from config/body.json, and all approved action routing for the session goes
through this object.
"""

import json
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BODY_CONFIG_PATH = PROJECT_ROOT / "config" / "body.json"

_DEFAULT_CONFIG = {"backend": "mock", "servo": {"enabled": False}}


def _load_config() -> dict:
    try:
        return json.loads(BODY_CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        print("[BODY CONTROLLER] config/body.json missing or malformed - using mock.")
        return _DEFAULT_CONFIG


class BodyController:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or _load_config()
        backend = config.get("backend", "mock")
        servo_cfg = config.get("servo", {})
        motion_cfg = config.get("motion", {})
        sim_cfg = config.get("sim", {})
        servo_on = servo_cfg.get("enabled", False)

        self._servo_body = None
        self._sim_body = None
        self._backend_name = "mock"

        if backend == "servo":
            if servo_on:
                from body.servo_body import ServoBody

                self._servo_body = ServoBody(servo_cfg, motion_cfg)
                self._backend_name = "servo"
                print("[BODY CONTROLLER] Backend: servo (opt-in)")
            else:
                print("[BODY CONTROLLER] Servo requested but servo.enabled is false - using mock.")
                print("[BODY CONTROLLER] Backend: mock")
        elif backend == "sim":
            from sim.sim_body import SimBody

            self._sim_body = SimBody(sim_cfg)
            self._backend_name = "sim"
            print("[BODY CONTROLLER] Backend: sim")
        elif backend == "mock":
            print("[BODY CONTROLLER] Backend: mock")
        else:
            print(f"[BODY CONTROLLER] Unknown backend '{backend}' - using mock.")
            print("[BODY CONTROLLER] Backend: mock")

    def execute_action(self, action: str):
        if self._servo_body is not None:
            return self._servo_body.execute_action(action)
        if self._sim_body is not None:
            return self._sim_body.execute_action(action)

        from body.mock_body import execute_action as mock_exec

        return mock_exec(action)

    def emit_cue(self, cue_id: str):
        if self._sim_body is not None:
            return self._sim_body.emit_cue(cue_id)
        if self._servo_body is not None:
            return {"latest_audio_cue": cue_id, "audio_state": "unsupported"}

        from body.mock_body import emit_cue as mock_cue

        return mock_cue(cue_id)

    def get_servo_positions(self) -> Optional[dict]:
        if self._servo_body is not None:
            return self._servo_body.get_positions()
        return None

    def get_status(self) -> dict:
        servo_body = self._servo_body
        sim_body = self._sim_body
        servo_ready = servo_body is not None and not servo_body.dry_run
        positions = servo_body.get_positions() if servo_body else {}
        sim_snapshot = sim_body.get_status() if sim_body else {}

        return {
            "backend": self._backend_name,
            "servo_enabled": servo_body is not None,
            "servo_ready": servo_ready,
            "servo_positions": positions,
            "sim": sim_snapshot,
        }

    def reset_sim(self) -> None:
        if self._sim_body is not None:
            self._sim_body.reset()
