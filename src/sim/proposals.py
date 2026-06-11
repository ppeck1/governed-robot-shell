from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from body.safety import evaluate_safety
from brain.intent import parse_intent
from brain.planner import choose_action
from runtime import RobotRuntime


@dataclass
class ProposalQueue:
    proposals: list[dict[str, Any]] = field(default_factory=list)
    _counter: int = 0

    def preview(self, command: str, runtime: RobotRuntime, *, source: str = "proposal_preview") -> dict[str, Any]:
        self._counter += 1
        raw_input = command.strip().lower()
        runtime._sync_sensors_from_body()
        intent = parse_intent(raw_input)
        action = choose_action(intent)
        safety = evaluate_safety(action, runtime.state)
        proposal = {
            "proposal_id": f"proposal_{self._counter:04d}",
            "source": source,
            "raw_input": raw_input,
            "proposed_intent": intent,
            "proposed_action": action,
            "confidence": 1.0,
            "rationale": "deterministic parser/planner preview",
            "safety_preview": safety.as_dict(),
            "review_status": "pending",
            "execution_allowed": False,
        }
        self.proposals.append(proposal)
        return proposal

    def list(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.proposals]

    def get(self, proposal_id: str) -> dict[str, Any] | None:
        for proposal in self.proposals:
            if proposal["proposal_id"] == proposal_id:
                return proposal
        return None

    def reject(self, proposal_id: str, reason: str = "") -> dict[str, Any] | None:
        proposal = self.get(proposal_id)
        if proposal is None:
            return None
        proposal["review_status"] = "rejected"
        proposal["review_reason"] = reason
        proposal["execution_allowed"] = False
        return proposal

    def approve_once(self, proposal_id: str, runtime: RobotRuntime) -> dict[str, Any] | None:
        proposal = self.get(proposal_id)
        if proposal is None:
            return None
        if proposal["review_status"] != "pending":
            return proposal
        proposal["review_status"] = "approved_once"
        proposal["execution_allowed"] = False
        event = runtime.process_command(proposal["raw_input"], source=f"proposal:{proposal_id}")
        proposal["execution_result"] = event
        return proposal
