# Governed Robot Shell

**This is an early architecture prototype, not a production robotics safety system.**
A governed robot-control shell where natural language is compressed into intent, validated by a layered safety system, and only then passed to physical or simulated hardware. The project's central design goal is that **no component — including the LLM — holds direct authority over actuators**.

Current build: **Phase 6A**
Default state: all hardware backends disabled, mock body, LLM disabled, behavior scheduler disabled.

---

## Quick Start

```bash
cd src
python main.py
```

Optional dependencies:

```bash
pip install opencv-python          # camera support
ollama pull llama3.2:3b            # local LLM intent classifier
```

---

## Architecture

The shell is organized into six independent subsystems plus a safety gate. Each subsystem owns its own state and configuration. None of them call each other directly — all coordination happens through `main.py` and `RobotState`.

```
CLI input
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  INTENT PIPELINE                                    │
│                                                     │
│  parse_intent()        rule-based keyword parser    │
│       │                                             │
│  LLMController         optional, advisory only      │
│       │                                             │
│  choose_action()       finite action vocabulary     │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
        check_safety(action, state)
                 │
        ┌────────┴─────────┐
      BLOCK              APPROVE
        │                  │
    log + print      subsystem dispatch
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    BodyController  PerceptionController  SensorController
    (servos/mock)   (camera)             (distance)
                                         │
                                         ▼
                                   RobotState.sensors
```

A second input path runs in parallel for scheduled behavior:

```
time / behavior tick
    │
    ▼
BehaviorScheduler.tick()
    │
check_safety(action, state)   ← same gate, no bypass
    │
BodyController.execute_action()
```

### Source Layout

```
src/
  brain/
    intent.py          keyword intent parser
    planner.py         intent → action name mapping
    state.py           RobotState dataclass
  body/
    safety.py          the safety gate
    body_controller.py selects mock or servo backend
    mock_body.py       prints mock output
    servo_body.py      PCA9685 expression backend
  perception/
    camera.py          OpenCV webcam backend
    perception_controller.py  session controller
  sensors/
    distance_sensor.py mock + future GPIO backend
    sensor_controller.py      session controller
  llm/
    intent_classifier.py    mock classifier
    ollama_classifier.py    local Ollama backend
    llm_controller.py       arbitration + gating
    decision_logger.py      JSONL audit log
  behavior/
    behavior_scheduler.py   passive expressive timer
  interface/
    cli.py             stdin input
  utils/
    logger.py          append-only event log

config/
  body.json            all subsystem configuration
  safety.json          action allowlists and sensor gates

data/
  logs/
    robot.log                  all command decisions
    llm_decisions.jsonl        LLM classification audit trail
  captures/
    capture_YYYYMMDD_HHMMSS.jpg  webcam frames
    capture_log.jsonl            capture metadata

tools/
  calibrate_servo.py            isolated servo calibration REPL
  warm_ollama.py                pre-warms Ollama model
  test_sensor_safety.py         sensor gate unit test
  test_behavior_scheduler.py    scheduler unit test
  test_behavior_safety.py       behavior → safety unit test
  test_llm_arbitration.py       LLM rule-first unit test
  test_llm_decision_log.py      JSONL logging unit test
  test_llm_response_validation.py  Ollama JSON parser unit test
  test_ollama_classifier.py     live Ollama integration test
```

---

## Authority Boundaries

Authority is the ability to cause hardware to move. The shell enforces a strict hierarchy about what holds it.

**What holds authority over hardware:**

- `check_safety()` — the only path to hardware execution. No subsystem bypasses it.
- `BodyController.execute_action()` — the only function that calls hardware. It is called exclusively after safety approval.

**What does NOT hold authority:**

| Component | What it may do | What it may not do |
|---|---|---|
| LLMController | Propose one intent from a fixed vocabulary | Emit actions, call hardware, modify state |
| BehaviorScheduler | Propose one action from a fixed allowed list | Enable movement, call LLM, bypass safety |
| PerceptionController | Capture frames, report status | Trigger body movement |
| SensorController | Read distance, update state.sensors | Trigger actions directly |
| RobotState | Hold current mode and sensor data | Make decisions |
| Planner | Map intent → action name | Choose hardware parameters |

The safety layer reads `RobotState` but nothing reads the safety layer except `main.py`. No subsystem can observe whether it was approved or blocked and react accordingly.

### The LLM Constraint in Detail

The LLM slot operates under four sequential constraints before its output reaches the planner:

1. **Rule-first arbitration** — if the rule parser produced a strong non-idle intent, the LLM is skipped entirely.
2. **Vocabulary gate** — the proposed intent must be in `allowed_intents`. Anything outside (servo commands, action names, custom strings) is rejected.
3. **Confidence gate** — proposals below `confidence_threshold` fall back to the rule intent.
4. **Planner + safety** — the validated intent still passes through the normal pipeline. LLM proposing `move` doesn't move anything; safety blocks `step_forward` in shell mode regardless.

---

## Safety Model

Safety evaluation follows a five-step ordered check. Each step can block. A request must pass all applicable steps to reach hardware.

```
1. Unknown action?          → fail closed. Unrecognized strings never execute.
2. Blocked actions list?    → block unless mode=mobile AND movement_enabled=True.
3. Mode allowlist?          → block if action not in current mode's allowed set.
4. Sensor gates?            → block movement-class actions if distance_status=critical.
5.                          → approve.
```

### Mode System

The robot operates in one of three modes stored in `RobotState.mode`:

| Mode | Movement allowed | Notes |
|---|---|---|
| `shell` | Never | Default. All locomotion blocked. |
| `expressive` | Never | Expression servos allowed. No locomotion. |
| `mobile` | Only if movement_enabled=True AND sensor gates pass | Not yet reachable via normal commands. |

Mode cannot be changed by command, LLM output, or sensor reading in the current build. It requires a config change and restart. This is intentional.

### Sensor Gates

Distance sensor readings flow into `RobotState.sensors` and are checked during step 4 of safety evaluation for movement-class actions:

| distance_status | Effect on movement |
|---|---|
| `safe` (> 30 cm) | Allowed (if mode permits) |
| `warning` (15–30 cm) | Allowed — informational only |
| `critical` (≤ 15 cm) | Blocked |
| missing (no poll yet) | Allowed by default (`unknown_blocks_movement: false`) |

The sensor gate is fully wired and tested. It applies in `mobile` mode. In the current default `shell` mode, locomotion is blocked at step 2 before the sensor gate is reached.

### Servo Backend Safety

The PCA9685 servo backend (`servo_body.py`) contains a second internal locomotion refusal independent of the safety gate:

```python
if action in _LOCOMOTION_ACTIONS:
    print("[SERVO BODY] Locomotion action refused by servo backend.")
    return
```

This is defense in depth — not a replacement for the safety gate.

---

## Execution Flow

### User command path

```
1.  CLI reads raw string
2.  behavior.notify_user_activity()        resets idle timer
3.  parse_intent(raw)                      rule parser → intent label
4.  llm.classify_intent(raw, intent, state)
        if strong rule intent → skip LLM
        else call classifier → validate → gate
        → final_intent
5.  choose_action(final_intent)            intent → action name
6.  check_safety(action, state)            5-step evaluation
7.  log_event(...)                         always logged regardless of approval
8.  if approved:
        dispatch to subsystem
        state.last_intent = intent
        state.last_action = action
    else:
        print SAFETY BLOCK reason
9.  maybe_background_tick()               almost always no-ops
```

### Behavior scheduler path (manual tick)

```
1.  behavior.tick(force=True)
        checks: disabled? max actions? cooldown? (idle bypassed by force)
        if all pass: weighted random selection from allowed_actions
2.  check_safety(action, state)           same gate
3.  log_event(..., source="behavior_scheduler")
4.  if approved: body.execute_action(action)
5.  behavior.record_execution(action)
```

### State update flow

```
SensorController.poll_distance()
    → state.sensors["distance_cm"]
    → state.sensors["distance_status"]
    → state.sensors["distance_timestamp"]

check_safety(action, state)
    reads state.mode
    reads state.movement_enabled
    reads state.sensors["distance_status"]

body.execute_action(action)
    → ServoBody.positions[channel] = angle   (in servo mode)
```

---

## Subsystems

### Body (`src/body/`)

Controls physical output. Selected at startup based on `config/body.json`.

**Mock backend** (default): prints descriptive output, no hardware required.

**Servo backend** (opt-in): drives a PCA9685 servo controller over I2C. Requires `"backend": "servo"` and `"servo.enabled": true`. If hardware libraries are unavailable, falls back to dry-run mode (prints angles and pulses, nothing moves).

Three expression channels currently configured:

| Channel | Name | Range | Home |
|---|---|---|---|
| 0 | head_yaw | 60°–120° | 90° |
| 1 | left_flutter | 75°–105° | 90° |
| 2 | right_flutter | 75°–105° | 90° |

Calibration utility: `python tools/calibrate_servo.py` (requires `"calibration.enabled": true` in config).

### Perception (`src/perception/`)

Read-only camera subsystem. OpenCV webcam capture. Disabled by default.

Enable: set `"camera.enabled": true` in `config/body.json`. Requires `pip install opencv-python`.

Captures save to `data/captures/capture_YYYYMMDD_HHMMSS.jpg`. Each capture (success or failure) appends a metadata record to `data/captures/capture_log.jsonl` when `diagnostics.save_metadata` is true.

Camera capture never triggers body movement. The two subsystems have no knowledge of each other.

### Sensors (`src/sensors/`)

Distance sensor subsystem. Mock backend only in current build. Disabled by default.

Enable: set `"distance_sensor.enabled": true` in `config/body.json`.

Mock returns the configured `mock_distance_cm` value. Classifications:

| Value | Status |
|---|---|
| > 30 cm | `safe` |
| 15–30 cm | `warning` |
| ≤ 15 cm | `critical` |

Sensor polls write to `RobotState.sensors`, which the safety layer reads when evaluating movement actions.

GPIO backend for HC-SR04 ultrasonic sensor is scaffolded (`"backend": "gpio"`) but not implemented.

### LLM (`src/llm/`)

Optional intent classifier. Disabled by default. Advisory only.

Two backends available:

**Mock** (`"backend": "mock"`): ~20 natural-language phrase mappings. Useful for development without running Ollama.

**Ollama** (`"backend": "ollama"`): local HTTP request to a running Ollama instance. Uses standard library only — no pip packages required. Response must be valid JSON containing an intent from `allowed_intents` with confidence in [0, 1]. Arrays, prose, markdown fences, and out-of-vocabulary intents are all rejected.

LLM decision log: `data/logs/llm_decisions.jsonl`. Records every classification: rule intent, LLM intent, confidence, final intent, whether it was used, and the rejection reason if not. No prompts or raw model responses are logged.

### Behavior Scheduler (`src/behavior/`)

Passive expressive timing layer. Disabled by default. Not an agent loop.

Proposes actions from a configured weighted list (`idle_flutter`, `play_chirp`, `head_turn_left_right`, `express_curious`). `step_forward` and all movement-prefixed names are filtered out at construction regardless of config.

Controls: `idle_after_seconds` (how long the robot must be idle before the scheduler fires), `min_action_cooldown_seconds` (minimum gap between scheduled actions), `max_actions_per_session` (hard cap).

All scheduled actions pass through safety before execution. `force=True` tick bypasses the idle threshold but not the cooldown and not safety.

---

## Command Reference

| Input | Intent | Action | Notes |
|---|---|---|---|
| `chirp` | chirp | play_chirp | approved |
| `look around` | scan | head_turn_left_right | approved |
| `act curious` | curious | express_curious | approved |
| `huh` | confused | express_confused | approved |
| `flutter` | idle | idle_flutter | approved |
| `wake` | wake | wake | approved |
| `sleep` | sleep | sleep | approved |
| `status` | status | report_status | full session snapshot |
| `camera status` | camera_status | report_camera_status | |
| `capture image` | capture_image | capture_camera_frame | saves JPG |
| `camera diagnostics` | camera_diagnostics | run_camera_diagnostics | probes device indices |
| `poll distance` | poll_distance | poll_distance_sensor | updates state.sensors |
| `distance status` | distance_status | report_distance_status | |
| `behavior status` | behavior_status | report_behavior_status | |
| `behavior tick` | behavior_tick | run_behavior_tick | forced scheduler tick |
| `walk forward` | move | step_forward | **blocked** in shell mode |
| `quit` | — | — | exits |

Natural-language variants are handled by the rule parser. Phrases the rule parser doesn't match fall to `idle`. With the Ollama backend enabled, some of those gaps are filled (e.g. "how close is that" → `distance_status`).

---

## Configuration

All configuration lives in `config/body.json` and `config/safety.json`. The shell reads both at startup. Changing config requires a restart.

Key flags:

```json
"backend": "mock"              body backend (mock | servo)
"servo.enabled": false         servo hardware opt-in
"camera.enabled": false        webcam opt-in
"distance_sensor.enabled": false  distance sensor opt-in
"llm.enabled": false           LLM classifier opt-in
"llm.backend": "mock"          mock | ollama
"behavior.enabled": false      behavior scheduler opt-in
"calibration.enabled": false   servo calibration REPL opt-in
```

Nothing is enabled by default. Each subsystem requires explicit opt-in.

---

## Logs

| File | Content | Format |
|---|---|---|
| `data/logs/robot.log` | Every command decision | Pipe-delimited, one line per event |
| `data/logs/llm_decisions.jsonl` | LLM classification metadata | JSONL, one object per classification |
| `data/captures/capture_log.jsonl` | Camera capture metadata | JSONL, one object per capture attempt |

Robot log fields: `timestamp | input | intent | action | approved | reason | source`

Source values: `user` (normal command), `behavior_scheduler` (scheduled action).

---

## Test Utilities

All tools run from the repo root without modifying production config.

```bash
python tools/test_sensor_safety.py        # sensor gate: 7/7
python tools/test_behavior_scheduler.py   # scheduler logic: 7/7
python tools/test_behavior_safety.py      # behavior → safety: 5/5
python tools/test_llm_arbitration.py      # rule-first arbitration: 8/8
python tools/test_llm_decision_log.py     # JSONL logging: 6/6
python tools/test_llm_response_validation.py  # Ollama parser: 13/13
python tools/test_ollama_classifier.py    # live Ollama (requires server)
python tools/calibrate_servo.py           # servo calibration (requires hardware + config)
python tools/warm_ollama.py               # pre-warms Ollama model
```

---

## Current Limitations

**No real locomotion.** `step_forward` is blocked in `shell` mode. The `mobile` mode exists in the safety config but cannot be entered through normal commands. Phase 6 locomotion work requires: a working leg mechanism, confirmed sensor hardware, and a deliberate mode-unlock sequence. The safety infrastructure for it (sensor gates, mode checks, movement_enabled flag) is already in place.

**No threading.** The behavior scheduler fires only on manual `behavior tick` or at the bottom of the command loop (where it almost always declines because the idle timer was just reset). Real background behavior requires a scheduler thread. The current architecture is compatible with threading — `tick()` is safe to call from another thread — but the thread itself hasn't been added.

**Single input source.** The shell reads from stdin. Voice, web dashboard, API endpoint, and sensor-triggered input are described in the architecture notes but not implemented.

**Mock sensors.** The distance sensor returns a configured static value. No HC-SR04 GPIO wiring exists. Touch/bump and IMU sensors are planned but not scaffolded.

**Expression servos not tested on hardware.** `servo_body.py` is fully implemented with bounded angles, home-return, and dry-run mode, but it hasn't been run against a physical PCA9685. The calibration tool exists for this purpose.

**LLM confidence calibration is model-dependent.** The 0.7 threshold was set for llama3.2:3b. Different models produce different confidence distributions. The threshold is configurable but hasn't been tuned against live hardware sessions.

**No servo position feedback.** `ServoBody.positions` tracks where angles were commanded, not where servos physically are. A real feedback loop requires encoders or potentiometers, which aren't in the current hardware plan.

**Camera and distance are not integrated.** The perception and sensor subsystems each report independently into status. No logic connects "camera sees obstacle" to the safety layer. That bridge would require image analysis (Phase 5+) and explicit wiring into `RobotState`.

---

## Future Work

The phases below follow from the current architecture without requiring structural changes.

**Phase 6B — Threading.** Add a `SchedulerThread` that calls `behavior.tick()` on `tick_interval_seconds`. The main loop's `record_execution()` callback and the thread-safe `tick()` design already support this. The command loop unblocks via timeout on `input()` or by moving to `select()`.

**Phase 6C — Mobile mode unlock sequence.** Define an explicit operator sequence (physical switch, confirmed sensor readings, explicit CLI override) that transitions `state.mode` from `shell` to `mobile`. This is the gate before any locomotion testing. The sensor gate in Phase 4D is already wired; it just needs a real distance sensor and `movement_enabled = True` to activate.

**Phase 6D — Leg mechanism.** Single leg on a bench. The planner already has `step_forward` in its vocabulary; the servo body needs leg channel mappings added. The safety layer already gates it on mode + movement_enabled + sensor status.

**Phase 5E — LLM transcript logging.** Opt-in logging of full prompts and raw model responses to a separate transcript file. The decision logger from Phase 5D separates audit metadata from verbose content; the transcript layer would extend it without touching existing logs.

**Phase 5F — Anthropic / OpenAI backend.** The `_load_classifier()` slot in `LLMController` accepts any object with a `.classify(text, context) -> dict` method. A cloud backend is a new classifier class. The vocabulary gate, confidence gate, and fallback logic already handle its output. The only new concern is latency — the 30-second timeout from Ollama would need to be shorter for a cloud API.

**Phase 4E — Touch and IMU sensors.** Follow the same pattern as Phase 4C: `TouchSensor` and `IMUSensor` classes, a `SensorController` expansion, new state fields, new sensor gate conditions in `safety.py`. The safety config already has a `sensor_gates` block designed for multiple sensor types.

**Phase 4F — Sensor-aware behavior.** The behavior scheduler currently ignores `RobotState.sensors`. A future mode could weight the action selection based on sensor state — e.g. increase `express_curious` weight when something is nearby, suppress `head_turn_left_right` when tilt is unstable. This is behavior modulation, not autonomy, as long as sensors influence weights rather than directly triggering actions.

**Vision interpretation.** Phase 4A established the camera infrastructure and capture pipeline. Feeding frames to a vision model (local or API) would produce descriptive state that enters `RobotState` alongside sensor data. The boundary rule remains: vision output informs state; state informs safety; safety gates action. Vision never directly calls the body.

