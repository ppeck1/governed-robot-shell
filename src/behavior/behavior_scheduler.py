"""
Behavioral scheduler — Phase 6A.

A session-scoped timing layer for passive expressive behaviors.
This is NOT an agent loop, planning engine, or autonomy system.

The scheduler may propose only pre-approved non-mobile expressive
actions, which must still pass through safety before execution.

The scheduler may NOT:
  - propose locomotion (step_forward or any movement action)
  - enable movement
  - call the LLM
  - inspect camera images
  - react to sensor readings as goals
  - bypass safety
  - mutate config
  - run continuous loops

Timing uses time.monotonic() for reliable cooldown/threshold tracking.
"""

import random
import time
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from brain.state import RobotState

_LOCOMOTION_PREFIXES = ("step_", "walk_", "move_", "crawl_", "run_")
_HARD_BLOCKED = {"step_forward"}


def _is_movement_action(action: str) -> bool:
    if action in _HARD_BLOCKED:
        return True
    return any(action.startswith(p) for p in _LOCOMOTION_PREFIXES)


def _no_action(reason: str) -> dict:
    return {"should_run": False, "action": None, "reason": reason}


def _propose(action: str, reason: str = "passive idle behavior") -> dict:
    return {"should_run": True, "action": action, "reason": reason}


class BehaviorScheduler:

    def __init__(self, state: Optional["RobotState"] = None,
                 config: Optional[dict] = None) -> None:
        self._state  = state
        cfg          = config or {}

        self.enabled:        bool  = cfg.get("enabled", False)
        self.mode:           str   = cfg.get("mode", "passive")
        self._idle_after:    float = float(cfg.get("idle_after_seconds", 20.0))
        self._cooldown:      float = float(cfg.get("min_action_cooldown_seconds", 15.0))
        self._max_actions:   int   = int(cfg.get("max_actions_per_session", 20))
        self._log_events:    bool  = cfg.get("log_behavior_events", True)

        # Build and validate action pool
        raw_allowed  = cfg.get("allowed_actions",
                               ["idle_flutter", "play_chirp",
                                "head_turn_left_right", "express_curious"])
        raw_blocked  = set(cfg.get("blocked_actions", ["step_forward"]))
        raw_weights  = cfg.get("weights", {})

        self._allowed: list = []
        self._weights: list = []

        valid = True
        for action in raw_allowed:
            if action in raw_blocked or _is_movement_action(action):
                print(f"[BEHAVIOR] Action '{action}' is blocked or movement — skipped.")
                continue
            w = float(raw_weights.get(action, 1.0))
            if w <= 0:
                continue
            self._allowed.append(action)
            self._weights.append(w)

        if not self._allowed:
            print("[BEHAVIOR] Invalid action config — no valid actions; scheduler disabled.")
            self.enabled = False
            valid = False

        # Runtime state
        now = time.monotonic()
        self.last_user_activity_ts: float   = now
        self.last_behavior_ts:      float   = 0.0
        self.action_count:          int     = 0
        self.last_action:           Optional[str] = None
        self.last_decision_reason:  str     = "not yet ticked"

        if self.enabled:
            print(f"[BEHAVIOR] Scheduler enabled: mode={self.mode} "
                  f"idle={self._idle_after}s cooldown={self._cooldown}s "
                  f"actions={self._allowed}")
        else:
            if valid:
                print("[BEHAVIOR] Scheduler disabled.")

    # ── User activity notification ────────────────────────────────────────────

    def notify_user_activity(self) -> None:
        """Reset idle timer. Call at the start of each user command."""
        self.last_user_activity_ts = time.monotonic()

    # ── Tick ─────────────────────────────────────────────────────────────────

    def tick(self, force: bool = False) -> dict:
        """
        Evaluate whether a scheduled behavior should run.

        force=True: bypass idle threshold only.
        Never bypasses: safety (external), allowed list, blocked list, cooldown.

        Returns a decision dict.
        """
        if not self.enabled:
            self.last_decision_reason = "behavior disabled"
            return _no_action("behavior disabled")

        now = time.monotonic()

        # Max action guard
        if self.action_count >= self._max_actions:
            self.last_decision_reason = "max actions reached"
            return _no_action("max actions reached")

        # Cooldown guard (not bypassed by force)
        since_last = now - self.last_behavior_ts
        if self.last_behavior_ts > 0 and since_last < self._cooldown:
            remaining = self._cooldown - since_last
            reason = f"cooldown active ({remaining:.1f}s remaining)"
            self.last_decision_reason = reason
            return _no_action(reason)

        # Idle threshold guard (bypassed by force)
        if not force:
            since_activity = now - self.last_user_activity_ts
            if since_activity < self._idle_after:
                remaining = self._idle_after - since_activity
                reason = f"idle threshold not reached ({remaining:.1f}s remaining)"
                self.last_decision_reason = reason
                return _no_action(reason)

        # Select action
        try:
            action = random.choices(self._allowed, weights=self._weights, k=1)[0]
        except (IndexError, ValueError):
            self.last_decision_reason = "action selection failed"
            return _no_action("action selection failed")

        # Final safety check on selected action (defense in depth)
        if action not in self._allowed or _is_movement_action(action):
            self.last_decision_reason = f"action '{action}' failed final check"
            return _no_action(f"action '{action}' failed final check")

        self.last_decision_reason = "passive idle behavior"
        return _propose(action, "passive idle behavior")

    def record_execution(self, action: str) -> None:
        """Call after a scheduled action is approved and executed."""
        self.last_behavior_ts = time.monotonic()
        self.last_action      = action
        self.action_count    += 1

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "behavior_enabled":      self.enabled,
            "behavior_mode":         self.mode,
            "behavior_action_count": self.action_count,
            "behavior_last_action":  self.last_action,
            "behavior_last_reason":  self.last_decision_reason,
        }
