from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class RobotState:
    mode: str = "shell"                     # shell | expressive | mobile
    movement_enabled: bool = False
    last_intent: Optional[str] = None
    last_action: Optional[str] = None
    sensors: dict = field(default_factory=dict)

    def snapshot(self) -> dict:
        return {
            "mode": self.mode,
            "movement_enabled": self.movement_enabled,
            "last_intent": self.last_intent,
            "last_action": self.last_action,
            "sensors": dict(self.sensors),
        }
