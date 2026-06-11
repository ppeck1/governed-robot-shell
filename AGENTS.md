# LLM Robot Shell - Codex Build Notes

## Project Identity

This project is a governed robot-control shell. It is not an LLM directly controlling hardware.

Core principle:

```text
language input
-> intent
-> planned action
-> safety validation
-> body execution
-> logging / state update
```

The LLM may propose or classify intent later. It must never directly control motors, servos, GPIO pins, or actuator angles.

## Current Build State

**Current phase:** Phase 3H - action registry and nonverbal cue kernel.

The current codebase implements a governed command pipeline with real robot state, config-based safety, a central action registry, symbolic nonverbal cue output, expanded mock behavior, an opt-in simulation body backend, deterministic scenarios, structured JSONL observability, replay/export, readiness manifests, emergency stop, review-only proposal previews, and a local FastAPI dashboard.

Known working examples:

```text
chirp        -> intent: chirp    -> action: play_chirp          -> approved
walk forward -> intent: move     -> action: step_forward         -> blocked (shell mode)
look around  -> intent: scan     -> action: head_turn_left_right -> approved
act curious  -> intent: curious  -> action: express_curious      -> approved
huh          -> intent: confused -> action: express_confused     -> approved
flutter      -> intent: idle     -> action: idle_flutter         -> approved
status       -> intent: status   -> action: report_status        -> approved
```

Default body is still mock-only. The simulator is opt-in through runtime/API construction or `config/body.json`. No real hardware should move yet.

"Voice" in this project means nonverbal cue output only: chirps, clicks, trills, sleepy tones, alert tones, and similar symbolic signals. It does not mean speech, STT, TTS, wake-word handling, or full verbal interaction.

## Architecture Contract

The system must preserve these layer boundaries at all times.

### Interface Layer

Accepts commands from the user.

- Current: CLI input and simulator dashboard text commands
- Future: voice, local app, LLM chat surface, sensor-triggered events

The interface layer must not call hardware, simulator bodies, servo channels, GPIO, or actuator values directly.

### Intent Layer

Converts raw input into a controlled intent label.

- Current: keyword parser
- Future: rule parser, LLM-assisted classifier, confidence scoring

The intent layer outputs intent labels only, never actuator commands.

### Planner Layer

Maps intent to an approved internal action name from a finite vocabulary.

```text
chirp   -> play_chirp
scan    -> head_turn_left_right
move    -> step_forward
curious -> express_curious
status  -> report_status
```

The planner must use a finite, explicit action vocabulary.

### Action Registry Layer

`brain/action_registry.py` is the code-level action authority. Every planner output must exist in the registry.

Each registered action declares category, allowed modes, backend support, movement requirements, emergency-stop behavior, and default cue.

### Safety Layer

Evaluates whether the planned action is allowed in the current robot state.

- Loads rules from `config/safety.json`
- Falls back to safe defaults if config is missing
- Unknown or unrecognized actions fail closed
- `step_forward` remains blocked unless mode is `mobile` and `movement_enabled` is `True`
- Safety must be state-aware before real movement is enabled

### Body Layer

Executes an approved action.

- Current: mock body by default, optional simulation body, explicit opt-in servo body
- Future: audio body, sensor body, motion body, tool arm body

Hardware body modules must never bypass safety.

### Audio Cue Layer

`body/audio_cues.py` defines symbolic nonverbal cue ids only:

- `chirp_ack`
- `chirp_blocked`
- `chirp_confused`
- `chirp_curious`
- `chirp_sleepy`
- `chirp_alert`
- `chirp_wake`
- `chirp_idle`

Cues are outputs, not authority paths. A cue can never approve, bypass, or cause movement.

### Simulation Layer

Provides a deterministic virtual robot and world for testing the governed pipeline.

- `SimWorld`: room bounds, obstacles, light, and sound sources
- `SimRobot`: pose, expression channels, audio/power state
- `SimObservation`: virtual sensor snapshot
- `SimBody`: applies approved finite actions to simulated state only

The dashboard and scenarios must submit text commands through `RobotRuntime`. They must not call `SimBody`, servo code, GPIO, or raw motion APIs directly.

### Event Kernel Layer

Simulator-era behavior is recorded through a single append-only event writer.

- Events use schema `robot_event.v0.2`.
- Events include `event_id`, `sequence`, `event_type`, `source`, `payload`, `state_before`, and `state_after`.
- Replay is deterministic from exported kernel events.
- Legacy text logs remain for operator readability.

### Logging Layer

Every command/action decision is logged.

Minimum log fields:

- timestamp
- raw input
- intent
- action
- approved / blocked
- reason

Structured simulator-era events are written to `data/logs/robot_events.jsonl`.

## Safety Doctrine

This project uses a governor model.

The robot must never interpret language as direct motor authority.

Bad:

```text
LLM -> servo angle
```

Good:

```text
LLM / user input -> intent -> action proposal -> safety gate -> bounded body command
```

Movement remains blocked until:

- State exists and is passed into safety check
- Config-based safety exists
- Sensor assumptions are explicit
- Emergency stop behavior is defined
- A test harness exists

Locomotion is not part of the current build. The safety layer requires mode, movement flag, emergency-stop clearance, motion-inhibit clearance, and front-clearance sensor readiness before approving `step_forward`; the sim backend still refuses `step_forward` directly as a second line of defense.

## Current Action Vocabulary

| Action | Available in shell? |
| --- | --- |
| play_chirp | yes |
| head_turn_left_right | yes |
| enter_idle_mode | yes |
| idle_flutter | yes |
| express_curious | yes |
| express_confused | yes |
| wake | yes |
| sleep | yes |
| report_status | yes |
| step_forward | no, blocked |

Unknown actions fail closed.

## Hardware Assumptions

Planned hardware path:

```text
PC or Raspberry Pi
-> Python shell
-> I2C
-> PCA9685 servo driver
-> external servo power supply (common ground)
-> servos
```

The PCA9685 controls servo signal only. Servos must have their own power supply.

First real hardware target:

- head yaw
- eyelid / wing / flutter servo
- small non-locomotion expression motion

Do not begin leg locomotion.

## Phase Roadmap

### Phase 1 - Shell complete

- CLI input, keyword intent parser, planner, safety blocklist, mock body, logging

### Phase 2 - State and Mock Behavior complete

- Real `RobotState` object
- State-aware safety check
- Config-based safety
- Expanded mock actions

### Phase 3 - Single Servo Expression

- `servo_body.py`
- PCA9685 I2C connection
- Bounded servo channel map
- Expression-only movement, no locomotion

### Phase 3F / Sim S0-S3 - Virtual Simulation Environment

- `runtime.py` shared governed command path
- `sim/` deterministic world, robot, observations, and scenarios
- `sim_api.py` FastAPI surface and static dashboard
- Structured JSONL event log
- Pytest coverage for pipeline, safety, sim backend, scenarios, API, and dashboard hooks

### Phase 3G / Sim S4-S7 - Governed Replay, Readiness, Proposals

- Single append-only event writer
- Event export and replay endpoints
- Sensor-aware safety with emergency stop and motion inhibit fields
- Simulator manifest and readiness endpoints
- Dashboard panels for gate, readiness, replay/export, and proposals
- Review-only proposal preview/approve/reject scaffold

### Phase 3H - Action Registry and Nonverbal Cue Kernel

- Central action registry for all planner actions
- Symbolic chirp cue vocabulary
- Source-aware `CommandEnvelope`
- Registry-driven safety metadata
- Mock cue output and sim cue tracking
- Preview mode that evaluates without body/cue execution

### Phase 4 - Sensors

- Ultrasonic distance, bump/touch, tilt/IMU, camera later
- Safety layer becomes sensor-aware

### Phase 5 - LLM Layer

- LLM enters as intent interpreter only
- May propose: intent, explanation, uncertainty
- May not command: servo channels, GPIO pins, raw motor values, actuator angles

### Phase 6 - Movement

- Only after safety, state, sensors, and expression are reliable
- Begin: single leg on bench, tethered low-power crawl
- Never: free locomotion before safety gates are proven

## Build Rules for Codex

1. Update this `AGENTS.md` every build session.
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
14. Simulator dashboards and scenarios must route through the governed command pipeline.

## Change Log

### 2026-06-11 - Build 12 (README screenshots / public repo sync)

- Reviewed current Phase 3H simulator/action-registry build state against local tests and dashboard behavior.
- Added README screenshots under `docs/screenshots/` for the simulator overview and governed command flow.
- Updated public-facing README status, quick start, architecture, safety, simulator endpoint, cue, and log sections.
- Verified tests still pass: 27 passing.
- No runtime behavior, safety behavior, hardware enablement, speech, STT, TTS, wake word, or locomotion behavior added.

### 2026-06-09 - Build 9 (Phase 3F / Sim S0-S3 virtual environment)

- Added shared `RobotRuntime` so CLI and API use the same intent/planner/safety/body/logging path.
- Added `sim` backend with deterministic `SimWorld`, `SimRobot`, `SimObservation`, and `SimBody`.
- Added FastAPI simulator surface: `/sim/state`, `/sim/command`, `/sim/reset`, `/sim/scenarios`, scenario run endpoints, and `/` dashboard.
- Added local static dashboard with a 3D-style canvas renderer, command controls, status panel, sensor panel, and event log.
- Added structured JSONL event logging at `data/logs/robot_events.jsonl`.
- Added pytest coverage for command mapping, safety gates, sim backend, scenario replay, API shape, and dashboard hooks.
- Mock remains default. Servo opt-in unchanged. Locomotion remains blocked and sim backend refuses it directly.

### 2026-06-09 - Build 10 (Phase 3G / Sim S4-S7 governed replay/readiness/proposals)

- Added single append-only event writer at `utils/events.py`.
- Added kernel events for command receipt, intent classification, action planning, safety gate evaluation, body application/refusal, sim observation, and scenario start/complete.
- Added replay/export surfaces: `/sim/events`, `/sim/export`, `/sim/replay`.
- Added `emergency_stop`, `motion_inhibited`, and sensor-aware movement gates to `RobotState` and safety.
- Added finite actions `set_emergency_stop` and `clear_emergency_stop`.
- Added robot-specific `/sim/manifest` and `/sim/readiness`.
- Added review-only proposal queue endpoints; preview does not execute, approve routes once through `RobotRuntime`.
- Dashboard now shows safety gate, readiness, replay/export, and proposal preview panels.
- Tests expanded to 18 passing. Mock remains default. No real hardware movement added.

### 2026-06-09 - Build 11 (Phase 3H action registry / nonverbal cues)

- Added `brain/action_registry.py` as the code-level source of truth for action metadata.
- Added `body/audio_cues.py` with chirp-only symbolic cue ids.
- Added `CommandEnvelope` support to `RobotRuntime`.
- Safety now uses registry metadata and includes action category plus selected cue in gate results.
- Mock backend prints `[MOCK CUE] cue_id`; sim backend tracks latest cue, audio state, and cue count.
- Preview mode evaluates parser/planner/safety without executing body actions or cues.
- Tests expanded to 27 passing.
- No speech, STT, TTS, wake word, real audio hardware, or locomotion behavior added.

### 2026-05-08 - Build 8 (Phase 3E status and observability)

- Added `status` intent mapping.
- Added `report_status` action to planner and all safety mode allowlists.
- Added `BodyController.get_status()`.
- Status remains read-only and never touches body hardware.

### 2026-05-08 - Builds 1-7

- Built the initial shell, state-aware safety, config-based allowlists, mock actions, servo backend skeleton, calibration tool, expression servo dry-run support, persistent body controller, and status observability.
