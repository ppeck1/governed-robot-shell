from __future__ import annotations

from typing import Final

CHIRP_ACK: Final = "chirp_ack"
CHIRP_BLOCKED: Final = "chirp_blocked"
CHIRP_CONFUSED: Final = "chirp_confused"
CHIRP_CURIOUS: Final = "chirp_curious"
CHIRP_SLEEPY: Final = "chirp_sleepy"
CHIRP_ALERT: Final = "chirp_alert"
CHIRP_WAKE: Final = "chirp_wake"
CHIRP_IDLE: Final = "chirp_idle"

CUE_VOCABULARY: Final = {
    CHIRP_ACK,
    CHIRP_BLOCKED,
    CHIRP_CONFUSED,
    CHIRP_CURIOUS,
    CHIRP_SLEEPY,
    CHIRP_ALERT,
    CHIRP_WAKE,
    CHIRP_IDLE,
}


def cue_for_blocked(*, unknown_action: bool = False) -> str:
    return CHIRP_CONFUSED if unknown_action else CHIRP_BLOCKED
