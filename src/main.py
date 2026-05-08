import json
from pathlib import Path

from interface.cli import get_user_input
from brain.intent import parse_intent
from brain.planner import choose_action
from brain.state import RobotState
from body.body_controller import BodyController
from body.safety import check_safety
from perception.perception_controller import PerceptionController
from sensors.sensor_controller import SensorController
from llm.llm_controller import LLMController
from behavior.behavior_scheduler import BehaviorScheduler
from utils.logger import log_event

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_behavior_config() -> dict:
    p = PROJECT_ROOT / "config" / "body.json"
    try:
        return json.loads(p.read_text()).get("behavior", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _last_capture_summary(meta):
    if meta is None:
        return None, None
    w, h = meta.get("actual_width"), meta.get("actual_height")
    return meta.get("success", False), (f"{w}x{h}" if (w and h) else None)


def print_status(state, body, perception, sensors, llm, behavior) -> None:
    body_s = body.get_status()
    perc_s = perception.get_status()
    sens_s = sensors.get_status()
    llm_s  = llm.get_status()
    beh_s  = behavior.get_status()
    positions = body_s.get("servo_positions", {})
    cap_ok, cap_size = _last_capture_summary(perc_s.get("last_capture_metadata"))

    print("\n[STATUS]")
    print(f"  mode              : {state.mode}")
    print(f"  movement_enabled  : {state.movement_enabled}")
    print(f"  last_intent       : {state.last_intent}")
    print(f"  last_action       : {state.last_action}")
    print(f"  backend           : {body_s['backend']}")
    print(f"  servo_enabled     : {body_s['servo_enabled']}")
    print(f"  servo_ready       : {body_s['servo_ready']}")
    if positions:
        print(f"  servo_positions   :")
        for ch, angle in positions.items():
            print(f"    {ch:<20} {angle:.1f}°")
    else:
        print(f"  servo_positions   : {{}}")
    print(f"  camera_enabled    : {perc_s['camera_enabled']}")
    print(f"  camera_ready      : {perc_s['camera_ready']}")
    print(f"  camera_device     : {perc_s['camera_device_index']}")
    print(f"  last_capture      : {perc_s['last_capture']}")
    print(f"  last_capture_ok   : {cap_ok}")
    print(f"  last_capture_size : {cap_size}")
    print(f"  distance_enabled  : {sens_s['enabled']}")
    print(f"  distance_backend  : {sens_s['backend']}")
    print(f"  distance_ready    : {sens_s['ready']}")
    print(f"  distance_cm       : {sens_s['last_distance_cm']}")
    print(f"  distance_status   : {sens_s['last_status']}")
    print(f"  distance_ts       : {sens_s['last_read_timestamp']}")
    print(f"  llm_enabled       : {llm_s['llm_enabled']}")
    print(f"  llm_backend       : {llm_s['llm_backend']}")
    print(f"  llm_last_used     : {llm_s['llm_last_used']}")
    print(f"  llm_last_intent   : {llm_s['llm_last_intent']}")
    print(f"  llm_confidence    : {llm_s['llm_last_confidence']}")
    print(f"  llm_last_reason   : {llm_s['llm_last_reason']}")
    if llm_s.get("llm_decision_log"):
        print(f"  llm_decision_log  : {llm_s['llm_decision_log']}")
    print(f"  behavior_enabled  : {beh_s['behavior_enabled']}")
    print(f"  behavior_mode     : {beh_s['behavior_mode']}")
    print(f"  behavior_actions  : {beh_s['behavior_action_count']}")
    print(f"  behavior_last     : {beh_s['behavior_last_action']}")
    print(f"  behavior_reason   : {beh_s['behavior_last_reason']}")


def print_camera_status(perception) -> None:
    s = perception.get_status()
    cap_ok, cap_size = _last_capture_summary(s.get("last_capture_metadata"))
    print("\n[CAMERA STATUS]")
    print(f"  camera_enabled    : {s['camera_enabled']}")
    print(f"  camera_ready      : {s['camera_ready']}")
    print(f"  camera_device     : {s['camera_device_index']}")
    print(f"  last_capture      : {s['last_capture']}")
    print(f"  last_capture_ok   : {cap_ok}")
    print(f"  last_capture_size : {cap_size}")


def print_distance_status(sensors, state) -> None:
    s = sensors.get_status()
    print("\n[DISTANCE STATUS]")
    print(f"  enabled           : {s['enabled']}")
    print(f"  backend           : {s['backend']}")
    print(f"  ready             : {s['ready']}")
    print(f"  distance_cm       : {s['last_distance_cm']}")
    print(f"  status            : {s['last_status']}")
    print(f"  timestamp         : {s['last_read_timestamp']}")
    print(f"  warning_threshold : {s['warning_distance_cm']} cm")
    print(f"  critical_threshold: {s['critical_distance_cm']} cm")
    if state.sensors:
        print(f"  state.sensors     : {state.sensors}")


def print_behavior_status(behavior) -> None:
    s = behavior.get_status()
    print("\n[BEHAVIOR STATUS]")
    print(f"  enabled        : {s['behavior_enabled']}")
    print(f"  mode           : {s['behavior_mode']}")
    print(f"  action_count   : {s['behavior_action_count']}")
    print(f"  last_action    : {s['behavior_last_action']}")
    print(f"  last_reason    : {s['behavior_last_reason']}")


def run_behavior_tick(behavior, body, state) -> None:
    """Execute a forced behavior tick through safety."""
    decision = behavior.tick(force=True)

    if not decision["should_run"]:
        print(f"[BEHAVIOR] No action: {decision['reason']}")
        return

    action   = decision["action"]
    approved, reason = check_safety(action, state)
    log_event("[behavior_tick]", "behavior", action, approved, reason,
              source="behavior_scheduler")

    if approved:
        print(f"[BEHAVIOR] Proposed action: {action}")
        body.execute_action(action)
        behavior.record_execution(action)
    else:
        print(f"[BEHAVIOR] Action '{action}' blocked by safety: {reason}")


def maybe_background_tick(behavior, body, state) -> None:
    """
    Attempt a background tick after each user command.
    Will almost always decline because user activity just reset the idle timer.
    No-op if behavior disabled.
    """
    if not behavior.enabled:
        return
    decision = behavior.tick(force=False)
    if not decision["should_run"]:
        return
    action   = decision["action"]
    approved, reason = check_safety(action, state)
    log_event("[background_tick]", "behavior", action, approved, reason,
              source="behavior_scheduler")
    if approved:
        print(f"\n[BEHAVIOR] Background action: {action}")
        body.execute_action(action)
        behavior.record_execution(action)


def main():
    print("LLM Robot Shell Online")
    print("Mode: shell | Movement: disabled\n")

    state      = RobotState()
    body       = BodyController()
    perception = PerceptionController()
    sensors    = SensorController(state)
    llm        = LLMController()
    behavior   = BehaviorScheduler(state, _load_behavior_config())

    while True:
        user_input = get_user_input()

        if user_input == "quit":
            print("Shutting down.")
            break

        # Reset idle timer at start of each command
        behavior.notify_user_activity()

        rule_intent    = parse_intent(user_input)
        classification = llm.classify_intent(user_input, rule_intent, state)
        intent         = classification["final_intent"]

        action = choose_action(intent)

        approved, reason = check_safety(action, state)

        log_event(user_input, intent, action, approved, reason, source="user")

        if approved:
            if action == "report_status":
                print_status(state, body, perception, sensors, llm, behavior)
            elif action == "report_camera_status":
                print_camera_status(perception)
            elif action == "run_camera_diagnostics":
                perception.run_camera_diagnostics()
            elif action == "capture_camera_frame":
                perception.capture_frame()
            elif action == "report_distance_status":
                print_distance_status(sensors, state)
            elif action == "poll_distance_sensor":
                sensors.poll_distance()
            elif action == "report_behavior_status":
                print_behavior_status(behavior)
            elif action == "run_behavior_tick":
                run_behavior_tick(behavior, body, state)
            else:
                body.execute_action(action)

            state.last_intent = intent
            state.last_action = action
        else:
            print(f"\n[SAFETY BLOCK] {reason}")

        # Background tick (usually no-ops — idle timer was just reset)
        maybe_background_tick(behavior, body, state)


if __name__ == "__main__":
    main()
