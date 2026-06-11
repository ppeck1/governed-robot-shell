from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionSpec:
    action_id: str
    category: str
    allowed_modes: tuple[str, ...]
    backend_support: tuple[str, ...]
    blocked_by_default: bool = False
    requires_movement_enabled: bool = False
    requires_front_clearance: bool = False
    allowed_during_emergency: bool = False
    default_cue: str = "chirp_ack"


ACTION_REGISTRY: dict[str, ActionSpec] = {
    "play_chirp": ActionSpec(
        action_id="play_chirp",
        category="audio_cue",
        allowed_modes=("shell", "expressive", "mobile"),
        backend_support=("mock", "sim"),
        default_cue="chirp_ack",
    ),
    "head_turn_left_right": ActionSpec(
        action_id="head_turn_left_right",
        category="expression",
        allowed_modes=("shell", "expressive", "mobile"),
        backend_support=("mock", "sim", "servo"),
    ),
    "enter_idle_mode": ActionSpec(
        action_id="enter_idle_mode",
        category="expression",
        allowed_modes=("shell", "expressive", "mobile"),
        backend_support=("mock", "sim", "servo"),
        default_cue="chirp_idle",
    ),
    "idle_flutter": ActionSpec(
        action_id="idle_flutter",
        category="expression",
        allowed_modes=("shell", "expressive", "mobile"),
        backend_support=("mock", "sim", "servo"),
        default_cue="chirp_idle",
    ),
    "express_curious": ActionSpec(
        action_id="express_curious",
        category="expression",
        allowed_modes=("shell", "expressive", "mobile"),
        backend_support=("mock", "sim", "servo"),
        default_cue="chirp_curious",
    ),
    "express_confused": ActionSpec(
        action_id="express_confused",
        category="expression",
        allowed_modes=("shell", "expressive", "mobile"),
        backend_support=("mock", "sim", "servo"),
        default_cue="chirp_confused",
    ),
    "wake": ActionSpec(
        action_id="wake",
        category="expression",
        allowed_modes=("shell", "expressive", "mobile"),
        backend_support=("mock", "sim", "servo"),
        default_cue="chirp_wake",
    ),
    "sleep": ActionSpec(
        action_id="sleep",
        category="expression",
        allowed_modes=("shell", "expressive", "mobile"),
        backend_support=("mock", "sim", "servo"),
        allowed_during_emergency=True,
        default_cue="chirp_sleepy",
    ),
    "report_status": ActionSpec(
        action_id="report_status",
        category="diagnostic",
        allowed_modes=("shell", "expressive", "mobile"),
        backend_support=("mock", "sim", "servo"),
        allowed_during_emergency=True,
        default_cue="chirp_ack",
    ),
    "set_emergency_stop": ActionSpec(
        action_id="set_emergency_stop",
        category="safety",
        allowed_modes=("shell", "expressive", "mobile"),
        backend_support=("mock", "sim", "servo"),
        allowed_during_emergency=True,
        default_cue="chirp_alert",
    ),
    "clear_emergency_stop": ActionSpec(
        action_id="clear_emergency_stop",
        category="safety",
        allowed_modes=("shell", "expressive", "mobile"),
        backend_support=("mock", "sim", "servo"),
        allowed_during_emergency=True,
        default_cue="chirp_ack",
    ),
    "step_forward": ActionSpec(
        action_id="step_forward",
        category="movement",
        allowed_modes=("mobile",),
        backend_support=("mock", "sim"),
        blocked_by_default=True,
        requires_movement_enabled=True,
        requires_front_clearance=True,
        default_cue="chirp_ack",
    ),
}


def get_action(action_id: str) -> ActionSpec | None:
    return ACTION_REGISTRY.get(action_id)


def known_actions() -> set[str]:
    return set(ACTION_REGISTRY)
