"""
LLM decision logger — Phase 5D.

Writes one JSONL record per classification call to an audit log.
Records metadata only — no raw prompts, no raw model responses.

The log is observational only. It does not affect planner or safety.
Never raises into the main loop; prints a warning on write failure.

Record shape:
  {
    "timestamp":       "2026-05-08T18:00:00",
    "user_input":      "how close is that",
    "rule_intent":     "idle",
    "llm_backend":     "mock",
    "llm_intent":      "distance_status",
    "llm_confidence":  0.80,
    "final_intent":    "distance_status",
    "used_llm":        true,
    "accepted":        true,
    "rejected_reason": null,
    "reason":          "mock_llm: Matched phrase: 'how close is that'"
  }
"""

import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def log_llm_decision(record: dict, log_path: str = "data/logs/llm_decisions.jsonl") -> None:
    """
    Append one decision record to the JSONL audit log.
    log_path is resolved relative to project root.
    Never raises — prints warning on write failure.
    """
    full_path = PROJECT_ROOT / log_path
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with full_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except OSError as exc:
        print(f"[LLM LOG] Failed to write decision log: {exc}")


def make_record(
    user_input:       str,
    rule_intent:      str,
    llm_backend:      str,
    llm_intent,
    llm_confidence,
    final_intent:     str,
    used_llm:         bool,
    accepted:         bool,
    rejected_reason,
    reason:           str,
) -> dict:
    return {
        "timestamp":       datetime.now().isoformat(timespec="seconds"),
        "user_input":      user_input,
        "rule_intent":     rule_intent,
        "llm_backend":     llm_backend,
        "llm_intent":      llm_intent,
        "llm_confidence":  llm_confidence,
        "final_intent":    final_intent,
        "used_llm":        used_llm,
        "accepted":        accepted,
        "rejected_reason": rejected_reason,
        "reason":          reason,
    }
