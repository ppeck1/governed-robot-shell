# LLM Robot Shell — Claude Build Notes

## Project Identity

This project is a governed robot-control shell. It is not an LLM directly controlling hardware.

Core principle:

```
language input
→ intent
→ planned action
→ safety validation
→ body execution
→ logging / state update
```

The LLM may propose or classify intent later. It must never directly control motors, servos, GPIO pins, or actuator angles.

---

## Current Build State

**Current phase:** Phase 3E — status and observability

The current codebase implements a governed command pipeline with real robot state, config-based safety, and expanded mock behavior.

Known working examples:

```
chirp         → intent: chirp    → action: play_chirp          → approved
walk forward  → intent: move     → action: step_forward         → blocked (shell mode)
look around   → intent: scan     → action: head_turn_left_right → approved
act curious   → intent: curious  → action: express_curious      → approved
huh           → intent: confused → action: express_confused     → approved
flutter       → intent: idle     → action: idle_flutter         → approved
```

Current body is mock-only. No real hardware should move yet.

---

## Architecture Contract

The system must preserve these layer boundaries at all times.

### Interface Layer
Accepts commands from the user.
- **Current:** CLI input
- **Future:** voice, web dashboard, local app, LLM chat surface, sensor-triggered events

The interface layer must not call hardware directly.

### Intent Layer
Converts raw input into a controlled intent label.
- **Current:** keyword parser
- **Future:** rule parser, LLM-assisted classifier, confidence scoring

The intent layer outputs intent labels only — never actuator commands.

### Planner Layer
Maps intent to an approved internal action name from a finite vocabulary.

```
chirp   → play_chirp
scan    → head_turn_left_right
move    → step_forward
curious → express_curious
```

The planner must use a finite, explicit action vocabulary.

### Safety Layer
Evaluates whether the planned action is allowed in the current robot state.

- Loads rules from `config/safety.json`
- Falls back to safe defaults if config is missing
- Unknown or unrecognized actions fail closed
- `step_forward` remains blocked unless mode is `mobile` AND `movement_enabled` is `True`
- Safety must be state-aware before real movement is enabled

### Body Layer
Executes an approved action.
- **Current:** mock body only
- **Future:** servo body, audio body, sensor body, motion body, tool arm body

Hardware body modules must never bypass safety.

### Logging Layer
Every command/action decision is logged.

**Minimum log fields:**
- timestamp
- raw input
- intent
- action
- approved / blocked
- reason

**Future log fields:** state snapshot, sensor snapshot, actor/source, hardware backend used

---

## Safety Doctrine

This project uses a governor model.

The robot must never interpret language as direct motor authority.

**Bad:**
```
LLM → servo angle
```

**Good:**
```
LLM / user input → intent → action proposal → safety gate → bounded body command
```

Movement remains blocked until:
- State exists and is passed into safety check ✓ (Phase 2)
- Config-based safety exists ✓ (Phase 2)
- Sensor assumptions are explicit
- Emergency stop behavior is defined
- A test harness exists

Locomotion is not part of the current build.

---

## Current Action Vocabulary

| Action               | Available in shell? |
|----------------------|---------------------|
| play_chirp           | ✓                   |
| head_turn_left_right | ✓                   |
| enter_idle_mode      | ✓                   |
| idle_flutter         | ✓                   |
| express_curious      | ✓                   |
| express_confused     | ✓                   |
| wake                 | ✓                   |
| sleep                | ✓                   |
| step_forward         | ✗ (blocked)         |

Unknown actions fail closed.

---

## Hardware Assumptions

Planned hardware path:

```
PC or Raspberry Pi
→ Python shell
→ I2C
→ PCA9685 servo driver
→ external servo power supply (common ground)
→ servos
```

The PCA9685 controls servo signal only. Servos must have their own power supply.

**First real hardware target:** expression-only movement
- head yaw
- eyelid / wing / flutter servo
- small non-locomotion motion

Do not begin leg locomotion.

---

## Phase Roadmap

### Phase 1 — Shell ✓ Complete
- CLI input, keyword intent parser, planner, safety blocklist, mock body, logging

### Phase 2 — State and Mock Behavior (current)
- Real `RobotState` object
- State-aware safety check
- Config-based safety (`config/safety.json`)
- Expanded mock actions
- Documentation filled in

### Phase 3 — Single Servo Expression
- `servo_body.py`
- PCA9685 I2C connection
- Bounded servo channel map
- Expression-only movement, no locomotion

### Phase 4 — Sensors
- Ultrasonic distance, bump/touch, tilt/IMU, camera later
- Safety layer becomes sensor-aware

### Phase 5 — LLM Layer
- LLM enters as intent interpreter only
- May propose: intent, explanation, uncertainty
- May not command: servo channels, GPIO pins, raw motor values, actuator angles

### Phase 6 — Movement
- Only after safety, state, sensors, and expression are reliable
- Begin: single leg on bench, tethered low-power crawl
- Never: free locomotion before safety gates are proven

---

## Build Rules for Claude

1. Update this `CLAUDE.md` every build session.
2. Do not add hardware movement before state-aware safety exists.
3. Do not let LLM output directly control hardware.
4. Keep action vocabulary finite and explicit.
5. Unknown actions must fail closed.
6. Prefer small, testable patches.
7. Preserve mock mode even after hardware mode exists.
8. Log all meaningful behavior changes.
9. Keep architecture docs aligned with code.
10. If changing safety behavior, document why.
11. All file paths that write project artifacts must resolve from project root, not current working directory.
12. Real hardware backends must be disabled by default and require explicit config opt-in.
13. Calibration scripts must be isolated from normal robot behavior and must use narrow motion limits.

---

## Change Log

### 2026-05-08 — Build 1 (Phase 1 complete)
- Initial shell created
- CLI, intent parser, planner, mock body, safety blocklist, logger wired
- Two live test commands logged: `chirp` (approved), `walk forward` (blocked)

### 2026-05-08 — Build 8 (Phase 3E status and observability)
- Added `status` intent mapping ("status", "state", "diagnostic", "what are you doing").
- Added `report_status` action to planner and all safety mode allowlists.
- Added `BodyController.get_status()` returning backend name, servo_enabled, servo_ready, positions.
- `report_status` routed through safety but dispatched to `print_status()` — never touches body hardware.
- `print_status()` reads state and body snapshot at moment of request; state updates after.
- Status after a blocked action shows the previous approved state (consistent, documented).
- Mock remains default. Servo opt-in unchanged. Locomotion blocked.

### 2026-05-08 — Build 7 (Phase 3D persistent body controller)
- Refactored `body_controller.py` into a session-scoped `BodyController` class.
- Config loaded once at init; backend selected and reported once at startup.
- `ServoBody` instantiated once per session, not once per action.
- Added `self.positions` dict to `ServoBody`; updated on every `_write` call.
- Added `ServoBody.get_positions()` and `BodyController.get_servo_positions()`.
- Updated `main.py`: `body = BodyController()` alongside `state = RobotState()`.
- Mock remains default. Servo opt-in unchanged. Locomotion blocked.

### 2026-05-08 — Build 6 (Phase 3C expression servo integration)
- Rewrote `servo_body.py` with full expression action implementations.
- Actions: head_turn_left_right, idle_flutter, express_curious, express_confused, wake, sleep, enter_idle_mode, play_chirp.
- All angles bounded by channel config. Channels return to home after action (configurable).
- `step_forward` refused at servo backend layer.
- Dry-run mode when hardware libraries unavailable — prints angles/pulses, nothing moves.
- Added `motion` config block to `body.json`: step_delay_seconds, return_home_after_action.
- Strengthened `body_controller.py`: reports active backend once; handles unknown backend, servo.enabled=false, missing config.
- Mock remains default. Servo backend requires `"backend": "servo"` AND `"servo.enabled": true`.
- No locomotion. No LLM integration.

### 2026-05-08 — Build 5 (Phase 3B servo calibration mode)
- Added `calibration` block to `config/body.json`. Disabled by default.
- Created `tools/calibrate_servo.py` — isolated calibration REPL for one servo channel.
- Calibration refuses to run unless explicitly enabled in config.
- Calibration runs in dry-run mode if hardware libraries are unavailable.
- Calibration bounds narrower than channel hardware limits (70°–110° vs 60°–120°).
- Calibration never touches normal robot actions or locomotion.
- Added `move_named_servo()` helper to `servo_body.py`.
- Normal robot behavior unchanged — still mock-only.
- Locomotion still blocked.

### 2026-05-08 — Build 4 (Phase 3A servo backend skeleton)
- Added `config/body.json` — body backend config, default `"backend": "mock"`.
- Added `src/body/body_controller.py` — selects mock or servo backend from config.
- Added `src/body/servo_body.py` — PCA9685 expression scaffold; safe import handling; locomotion refused at backend layer; bounded angle helper.
- Updated `src/main.py` to import `execute_action` from `body_controller`.
- Mock backend remains default. Servo backend requires `"backend": "servo"` and `"servo.enabled": true`.
- No real hardware movement enabled.
- Locomotion still blocked.

### 2026-05-08 — Build 3 (Phase 2.1 cleanup)
- Fixed logger path so all runs write to repo-root `data/logs/robot.log`.
- Removed accidental `src/data/` directory created by running from `src/`.
- Confirmed Phase 2 mock action pipeline works from both `repo root` and `src/`.
- Confirmed locomotion remains blocked in shell mode.
- No hardware control added.

### 2026-05-08 — Build 2 (Phase 2 begin)
- `CLAUDE.md` created at repo root
- `RobotState` dataclass implemented in `src/brain/state.py`
- `config/safety.json` created with mode-aware allowed action lists
- `src/body/safety.py` updated: loads config, state-aware, fails closed on unknown actions
- `src/brain/intent.py` expanded: broader keyword coverage
- `src/brain/planner.py` expanded: full action vocabulary, unknown intent → idle_flutter
- `src/body/mock_body.py` expanded: descriptive per-action mock output
- `src/main.py` updated: instantiates RobotState, passes state into safety, updates state after execution
- All notes files filled: README, architecture, safety-rules, build-log, hardware-inventory
