from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from body.body_controller import BodyController
from body.safety import evaluate_safety
from brain.intent import parse_intent
from brain.planner import choose_action
from brain.state import RobotState
from utils.events import EventWriter, replay_command_events
from utils.logger import log_event


@dataclass(frozen=True)
class CommandEnvelope:
    raw_input: str
    source: str = "cli"
    authority: str = "operator"
    execution_mode: str = "execute"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class RobotRuntime:
    """Session runtime for the governed command pipeline."""

    def __init__(
        self,
        *,
        state: RobotState | None = None,
        body: BodyController | None = None,
        body_config: dict[str, Any] | None = None,
    ) -> None:
        self.state = state or RobotState()
        self.body = body or BodyController(config=body_config)
        self.event_history: list[dict[str, Any]] = []
        self.event_writer = EventWriter()
        self._sync_sensors_from_body()

    def process_command(self, raw_input: str | CommandEnvelope, *, source: str = "cli") -> dict[str, Any]:
        envelope = raw_input if isinstance(raw_input, CommandEnvelope) else CommandEnvelope(raw_input=raw_input, source=source)
        user_input = envelope.raw_input.strip().lower()
        source = envelope.source
        state_before = self.state.snapshot()
        self.event_writer.write(
            "command_received",
            source=source,
            payload={
                "raw_input": user_input,
                "authority": envelope.authority,
                "execution_mode": envelope.execution_mode,
                "created_at": envelope.created_at,
            },
            state_before=state_before,
        )

        intent = parse_intent(user_input)
        self.event_writer.write(
            "intent_classified",
            source=source,
            payload={"raw_input": user_input, "intent": intent},
            state_before=state_before,
        )

        action = choose_action(intent)
        self.event_writer.write(
            "action_planned",
            source=source,
            payload={"intent": intent, "action": action},
            state_before=state_before,
        )

        self._sync_sensors_from_body()
        safety = evaluate_safety(action, self.state)
        self.event_writer.write(
            "safety_gate_evaluated",
            source=source,
            payload=safety.as_dict(),
            state_before=state_before,
        )

        body_result: dict[str, Any] | None = None
        cue_result: dict[str, Any] = {}
        selected_cue = safety.selected_cue
        if envelope.execution_mode == "preview":
            body_result = {"preview_only": True}
            self.event_writer.write(
                "command_previewed",
                source=source,
                payload={"action": action, "approved": safety.approved, "reason": safety.reason, "selected_cue": selected_cue},
                state_before=state_before,
                state_after=self.state.snapshot(),
            )
        elif safety.approved:
            if action == "set_emergency_stop":
                self.state.emergency_stop = True
                body_result = {"emergency_stop": True}
            elif action == "clear_emergency_stop":
                self.state.emergency_stop = False
                body_result = {"emergency_stop": False}
            elif action == "report_status":
                body_result = {"status_only": True}
            else:
                result = self.body.execute_action(action)
                body_result = result if isinstance(result, dict) else {}

            cue_result = self.body.emit_cue(selected_cue)
            self._sync_sensors_from_body()
            self.state.last_intent = intent
            self.state.last_action = action
            self.event_writer.write(
                "body_action_applied",
                source=source,
                payload={"action": action, "body_result": body_result or {}, "selected_cue": selected_cue, "cue_result": cue_result},
                state_before=state_before,
                state_after=self.state.snapshot(),
            )
        else:
            cue_result = self.body.emit_cue(selected_cue)
            self._sync_sensors_from_body()
            self.event_writer.write(
                "body_action_refused",
                source=source,
                payload={"action": action, "reason": safety.reason, "selected_cue": selected_cue, "cue_result": cue_result},
                state_before=state_before,
                state_after=self.state.snapshot(),
            )

        self._sync_sensors_from_body()
        self.event_writer.write(
            "sim_observed",
            source=source,
            payload={"sensors": dict(self.state.sensors)},
            state_before=state_before,
            state_after=self.state.snapshot(),
        )

        event = {
            "source": source,
            "raw_input": user_input,
            "intent": intent,
            "action": action,
            "approved": safety.approved,
            "reason": safety.reason,
            "envelope": {
                "source": source,
                "authority": envelope.authority,
                "execution_mode": envelope.execution_mode,
                "created_at": envelope.created_at,
            },
            "selected_cue": selected_cue,
            "gate": safety.as_dict(),
            "state": self.state.snapshot(),
            "body": self.body.get_status(),
            "body_result": body_result or {},
            "cue_result": cue_result,
        }
        self.event_history.append(event)
        log_event(user_input, intent, action, safety.approved, safety.reason)
        return event

    def snapshot(self) -> dict[str, Any]:
        status = self.body.get_status()
        return {
            "state": self.state.snapshot(),
            "body": status,
            "events": list(self.event_history),
            "event_log": list(self.event_writer.events),
            "last_event": self.event_history[-1] if self.event_history else None,
            "last_kernel_event": self.event_writer.events[-1] if self.event_writer.events else None,
        }

    def export(self) -> dict[str, Any]:
        return {
            "export_schema": "robot_sim_export.v0.2",
            "snapshot": self.snapshot(),
            "event_log": list(self.event_writer.events),
        }

    def replay(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        baseline = RobotState().snapshot()
        return {
            "replay_schema": "robot_sim_replay.v0.2",
            "event_count": len(events),
            "final_state": replay_command_events(events, baseline),
        }

    def _sync_sensors_from_body(self) -> None:
        sim_snapshot = self.body.get_status().get("sim") or {}
        sensors = sim_snapshot.get("sensors")
        if isinstance(sensors, dict):
            self.state.sensors = dict(sensors)
