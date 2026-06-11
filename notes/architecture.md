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

## Virtual Simulator

The simulator is an opt-in body backend and API surface. It is not an alternate authority path.

```text
dashboard/API command
  -> RobotRuntime.process_command()
  -> intent parser
  -> planner
  -> safety
  -> BodyController
  -> SimBody
```

`SimBody` updates only virtual robot state. It refuses `step_forward` directly as a second line of defense. The dashboard reads snapshots from `/sim/state` and sends natural-language commands to `/sim/command`; it never sends raw servo angles, GPIO values, or actuator commands.

Structured event records are appended to `data/logs/robot_events.jsonl` alongside the legacy text log.

## Event Kernel, Replay, And Readiness

Simulator-era events are written through `utils/events.py`. The kernel event stream is append-only and exported through `/sim/export`.

Replay is currently snapshot-based: every event with `state_after` advances the replayed state. This keeps replay deterministic while the simulator is early and avoids introducing a database.

Readiness is exposed through `/sim/readiness`. It is advisory only and never changes robot state or safety decisions.

## Proposal Scaffold

`/sim/proposals/preview` creates a review-only proposal from a text command. It runs the same parser/planner/safety preview but does not execute. Approving a proposal sends the original text command through `RobotRuntime` exactly once. Rejection never mutates robot state.

## Action Registry and Nonverbal Cues

`brain/action_registry.py` is the code-level source of truth for action metadata. Planner outputs must be present in the registry before safety will approve them.

The cue layer is nonverbal only. `body/audio_cues.py` defines symbolic chirp ids such as `chirp_ack`, `chirp_blocked`, and `chirp_alert`. Cues are emitted as outputs after a safety decision; they do not create authority and cannot cause motion.

Mock mode prints cue ids. Sim mode records latest cue state. Servo mode remains audio-neutral.
