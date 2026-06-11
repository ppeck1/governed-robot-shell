from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "data" / "logs"
EVENT_LOG_FILE = LOG_DIR / "robot_events.jsonl"
EVENT_SCHEMA_VERSION = "robot_event.v0.2"


class EventWriter:
    """Append-only in-memory and JSONL event writer."""

    def __init__(self) -> None:
        self._sequence = 0
        self.events: list[dict[str, Any]] = []

    def write(
        self,
        event_type: str,
        *,
        source: str,
        payload: dict[str, Any] | None = None,
        state_before: dict[str, Any] | None = None,
        state_after: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._sequence += 1
        event = {
            "event_id": f"evt_{self._sequence:06d}",
            "sequence": self._sequence,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "schema_version": EVENT_SCHEMA_VERSION,
            "event_type": event_type,
            "source": source,
            "payload": payload or {},
            "state_before": state_before or {},
            "state_after": state_after or {},
        }
        self.events.append(event)
        _append_jsonl(event)
        return event


def _append_jsonl(event: dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def replay_command_events(events: list[dict[str, Any]], baseline: dict[str, Any]) -> dict[str, Any]:
    """Replay state snapshots from command events.

    The event stream is append-only. For now, replay is snapshot-based: events
    that carry a non-empty state_after become the next state. This is stable
    and deterministic while the simulator is still early.
    """
    state = dict(baseline)
    for event in events:
        state_after = event.get("state_after") or {}
        if state_after:
            state = state_after
    return state
