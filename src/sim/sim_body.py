from __future__ import annotations

from typing import Any

from .models import SimRobot, SimWorld, build_observation


class SimBody:
    """Deterministic virtual body backend.

    This backend is intentionally expression-first. Locomotion actions are
    refused here as a second line of defense, even if called directly.
    """

    def __init__(self, sim_config: dict[str, Any] | None = None) -> None:
        config = sim_config or {}
        self.world = SimWorld(**config.get("world", {}))
        self.robot = SimRobot()
        self.last_action: str | None = None

    def execute_action(self, action: str) -> dict[str, Any]:
        if action == "step_forward":
            self.last_action = action
            return {"refused": True, "reason": "sim backend refuses locomotion"}

        dispatch = {
            "play_chirp": self._play_chirp,
            "head_turn_left_right": self._scan,
            "idle_flutter": self._idle_flutter,
            "express_curious": self._curious,
            "express_confused": self._confused,
            "wake": self._wake,
            "sleep": self._sleep,
            "enter_idle_mode": self._idle,
        }
        handler = dispatch.get(action)
        if handler:
            handler()
        self.robot.action_count += 1
        self.last_action = action
        return self.snapshot()

    def get_status(self) -> dict[str, Any]:
        return self.snapshot()

    def emit_cue(self, cue_id: str) -> dict[str, Any]:
        self.robot.latest_audio_cue = cue_id
        self.robot.audio_state = "cue"
        self.robot.cue_count += 1
        return {"latest_audio_cue": cue_id, "audio_state": "cue", "cue_count": self.robot.cue_count}

    def snapshot(self) -> dict[str, Any]:
        observation = build_observation(self.world, self.robot)
        return {
            "world": self.world.snapshot(),
            "robot": self.robot.snapshot(),
            "sensors": observation.snapshot(),
            "last_action": self.last_action,
        }

    def reset(self) -> None:
        self.robot = SimRobot()
        self.last_action = None

    def _play_chirp(self) -> None:
        self.robot.audio_state = "chirp"
        self.robot.expression = "bright"

    def _scan(self) -> None:
        self.robot.head_yaw_degrees = 0.0
        self.robot.expression = "scanning"

    def _idle_flutter(self) -> None:
        self.robot.left_flutter_degrees = -6.0
        self.robot.right_flutter_degrees = 6.0
        self.robot.expression = "idle"

    def _curious(self) -> None:
        self.robot.head_yaw_degrees = 14.0
        self.robot.left_flutter_degrees = 5.0
        self.robot.right_flutter_degrees = 5.0
        self.robot.expression = "curious"

    def _confused(self) -> None:
        self.robot.head_yaw_degrees = -10.0
        self.robot.left_flutter_degrees = -8.0
        self.robot.right_flutter_degrees = 8.0
        self.robot.expression = "confused"

    def _wake(self) -> None:
        self.robot.power_state = "awake"
        self.robot.audio_state = "idle"
        self.robot.expression = "neutral"
        self.robot.head_yaw_degrees = 0.0
        self.robot.left_flutter_degrees = 0.0
        self.robot.right_flutter_degrees = 0.0

    def _sleep(self) -> None:
        self.robot.power_state = "sleeping"
        self.robot.expression = "sleep"
        self.robot.left_flutter_degrees = -12.0
        self.robot.right_flutter_degrees = -12.0

    def _idle(self) -> None:
        self.robot.audio_state = "idle"
        self.robot.expression = "idle"
