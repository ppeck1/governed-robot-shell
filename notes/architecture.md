# Architecture

## Pipeline

```
user input (CLI)
  ↓
interface/cli.py       — reads and cleans input
  ↓
brain/intent.py        — keyword → intent label
  ↓
brain/planner.py       — intent → action name
  ↓
body/safety.py         — action + state → approved/blocked
  ↓
body/mock_body.py      — executes approved action (mock)
  ↓
utils/logger.py        — writes decision to log
  ↓
brain/state.py         — state updated after execution
```

## Module Responsibilities

| Module              | Responsibility                                      |
|---------------------|-----------------------------------------------------|
| interface/cli.py    | Accept and normalize user input. No logic.          |
| brain/intent.py     | Map raw text to a controlled intent label.          |
| brain/planner.py    | Map intent to a finite action name.                 |
| brain/state.py      | Hold current robot state (mode, flags, sensors).    |
| body/safety.py      | Approve or block actions based on state + config.   |
| body/mock_body.py   | Print mock output for approved actions.             |
| utils/logger.py     | Append structured decision record to log file.      |
| config/safety.json  | Declarative action allowlist per mode.              |

## Hard Rules

- The interface layer does not call hardware.
- The intent layer outputs labels, not commands.
- The planner uses a finite, explicit vocabulary.
- The safety layer is the only gate between intent and execution.
- LLM (future) may only propose intent — never servo angles or GPIO values.
- Unknown actions fail closed.

## Body Backend Layer

The body backend is selected through `config/body.json`.

```
body_controller.py
  ├── backend = "mock"  →  mock_body.py       (default)
  └── backend = "servo" and servo.enabled = true  →  servo_body.py
```

Default backend is always mock. Hardware backend must be explicitly enabled in config.

Hardware backend must never bypass the safety layer — safety runs before `body_controller` is called.

`servo_body.py` refuses locomotion actions internally as a second line of defense.

## Expression Servo Backend

When explicitly enabled (`"backend": "servo"`, `"servo.enabled": true`), the servo backend executes bounded expression actions using named channels from config.

Expression actions are still routed through the normal safety layer before reaching the body backend — the body_controller is never called for a blocked action.

If hardware libraries are unavailable, ServoBody enters dry-run mode automatically. Angles and pulse values are printed; nothing moves.

Channels return to home after each action unless `motion.return_home_after_action` is `false` in config.

## Persistent Body Controller

`BodyController` is initialized once at startup alongside `RobotState`.
It owns the selected backend for the full runtime session.

```
main.py
  state = RobotState()
  body  = BodyController()      ← one instance, initialized once
      │
      ├── mock mode   → mock_body.execute_action()
      └── servo mode  → ServoBody instance (one per session)
                            └── self.positions  ← tracks channel angles
```

This prevents repeated hardware initialization and lets `ServoBody`
maintain session-local state — specifically current channel positions,
which will be needed for smooth incremental motion in later phases.

## Status and Observability

The shell includes a read-only `report_status` action that reports current session state, selected body backend, servo readiness, and last known servo positions.

Status is routed through the normal safety layer (it must be in the mode's allowlist) but is dispatched to `print_status()` in `main.py` rather than the body backend — no hardware is touched.

This gives hardware testing a low-risk diagnostic surface: run `status` before and after any expression action to confirm channel positions are tracking correctly.

## Perception Layer

The perception subsystem is a separate session-scoped controller, initialized alongside `RobotState` and `BodyController`.

```
main.py
  state      = RobotState()
  body       = BodyController()
  perception = PerceptionController()   ← new
      └── Camera (OpenCV)
              ├── capture_frame()  → data/captures/capture_YYYYMMDD_HHMMSS.jpg
              └── get_status()     → ready, last_capture
```

Perception may: observe, capture, report, persist sensor data.

Perception may NOT: directly trigger movement, bypass safety, act autonomously.

Camera actions (`report_camera_status`, `capture_camera_frame`) are routed through safety like all other actions but dispatched to `PerceptionController`, never to the body backend.

Current perception backend: webcam via OpenCV.

## Camera Diagnostics and Metadata

Camera diagnostics allow safe local probing of available webcam indices without streaming or saving images. Each probe index is opened, queried for dimensions, and released — no frames are captured, no preview windows opened.

Captures produce structured metadata records (success or failure) stored on the `Camera` instance as `last_capture_metadata`. If `diagnostics.save_metadata` is true in config, each record is also appended as a JSON line to `data/captures/capture_log.jsonl` using a project-root-relative path.

This gives hardware testing a persistent audit trail: if a capture produces an unexpected size or fails intermittently, the JSONL log shows the exact timestamps and dimensions without relying on console output.

## Sensor Layer

The sensor subsystem provides environmental state inputs to `RobotState`.

```
main.py
  sensors = SensorController(state)   ← holds RobotState reference
      └── DistanceSensor (mock | gpio future)
              ├── poll_distance()  → classifies: safe / warning / critical
              └── get_status()     → ready, last_distance_cm, last_status
                       ↓
              state.sensors["distance_cm"]
              state.sensors["distance_status"]
              state.sensors["distance_timestamp"]
```

Sensor data flows into `RobotState.sensors` and may later inform safety decisions, but sensors do not autonomously trigger body actions in the current architecture. The safety layer will query `state.sensors` explicitly when sensor-aware gating is implemented.

## Sensor-Aware Safety

Sensor readings flow into `RobotState.sensors` via `SensorController`.
The safety layer reads that state when evaluating movement-class actions.

```
sensor poll
  → SensorController.poll_distance()
  → state.sensors["distance_status"] = "critical" | "warning" | "safe"
          ↓
  check_safety(action, state)
    1. unknown action?         → fail closed
    2. blocked_actions list?   → block (unless mobile + movement_enabled)
    3. mode allowlist?         → block if not in mode
    4. sensor gates?           → block if distance_status == "critical"
    5.                         → approve
```

Sensors constrain approval — they do not initiate movement.

## LLM Intent Layer

The LLM controller sits between the rule parser and the planner.

```
CLI input
  → parse_intent()          rule parser  (always runs first)
  → llm.classify_intent()   advisory layer (disabled by default)
      ├── validate: in allowed_intents?     → reject if not
      ├── validate: confidence >= threshold? → reject if not
      └── fallback to rule_intent if rejected (configurable)
  → final_intent
  → choose_action()         planner (authoritative)
  → check_safety()          safety  (authoritative)
  → subsystem dispatch
```

The LLM may only propose one intent from the finite `allowed_intents` list. It may not emit actions, modify state, call hardware, or bypass safety. Planner and safety remain authoritative regardless of LLM output.

## Local Ollama Intent Backend

The Ollama backend is an optional local classifier that extends the Phase 5A LLM slot.

```
user input
  → OllamaIntentClassifier.classify()
      ├── build prompt (system + allowed list + user text + context)
      ├── POST /api/generate to localhost:11434
      ├── parse response:
      │     try direct json.loads → reject if array
      │     fallback: regex extract first {...} block
      │     strip markdown fences
      ├── validate fields: intent ∈ allowed, confidence ∈ [0,1]
      └── return {intent, confidence, source, reason}
  → LLMController vocabulary gate (second line of defense)
  → LLMController confidence gate
  → final_intent → planner
```

Ollama uses standard library HTTP only — no extra pip packages required.
Ollama never calls hardware or tools directly.
Connection failures fall back to rule intent immediately.

## Rule-First LLM Arbitration

The LLM layer is subordinate to deterministic parsing.

```
parse_intent(raw)  →  rule_intent
                           │
               ┌───────────┴───────────┐
          strong?                    idle?
        (in rule_strong_intents)   (not matched)
               │                       │
         skip LLM                  call LLM
         final = rule_intent        validate → gate
                                    final = llm_intent (if accepted)
                                    final = rule_intent (if rejected)
```

Strong intents: scan, chirp, sleep, wake, curious, confused, move, status,
camera_status, capture_image, camera_diagnostics, distance_status, poll_distance.

The LLM fills gaps — it does not override clean deterministic matches.

## LLM Decision Logging

Every `classify_intent()` call writes one structured record to `data/logs/llm_decisions.jsonl`. This provides a persistent audit trail of how raw input became final intent.

```
classify_intent(user_input, rule_intent, state)
  → arbitration result
  → _write_log()
      → make_record()  ← metadata only, no prompt, no raw response
      → append to data/logs/llm_decisions.jsonl
```

The log is observational only. It does not affect planner or safety behavior.
Full prompt and raw response logging are reserved for a future transcript phase.

## Behavioral Scheduler

The behavioral scheduler is a session-scoped timing layer for passive expressive behaviors.

```
main.py
  behavior = BehaviorScheduler(state, config)

Per command:
  behavior.notify_user_activity()    ← resets idle timer

Manual or background:
  decision = behavior.tick(force?)
    ├── disabled?            → no action
    ├── max actions?         → no action
    ├── cooldown active?     → no action
    ├── idle threshold?      → no action (unless force=True)
    └── weighted_random()    → proposed action
          ↓
  check_safety(action, state)        ← still required
          ↓
  body.execute_action(action)        ← only if approved
  behavior.record_execution(action)
  log_event(..., source="behavior_scheduler")
```

This is NOT an agent loop. The scheduler does not plan, reason, call the LLM,
inspect perception, or initiate movement. It only proposes safe expressive
actions from a fixed configured list, which must still pass through safety.
