# Safety Rules

## Shell Phase (current)

- Mode is `shell` by default.
- `movement_enabled` is `False` by default.
- `step_forward` is in the global blocked list regardless of mode allowlist.
- Locomotion is only possible in `mobile` mode with `movement_enabled = True`.
- Unknown actions fail closed — not approved, not partially executed.

## Fail-Closed Behavior

If an action is not recognized in the known action vocabulary, it is blocked.  
If the config file is missing or malformed, safe defaults apply.  
Safety must never silently pass an unknown action.

## Future Sensor Gates (Phase 4+)

Before locomotion is unblocked, the safety layer must additionally verify:
- distance sensor clear
- tilt/IMU within bounds
- battery voltage within range
- no thermal alarm
- emergency stop not active
- operator override present

## Doctrine

The safety layer is the most important module. Its job is not to be convenient —  
its job is to be the last line before the body does something irreversible.

## Hardware Backend Rules

- Mock backend is the default and always safe.
- Servo backend requires `"backend": "servo"` AND `"servo.enabled": true` in `config/body.json`.
- Missing or malformed config falls back to mock.
- Missing hardware libraries (adafruit_pca9685, board, busio) must fail safely — no crash.
- Servo angles must be bounded by per-channel `min_angle` / `max_angle` from config.
- Servo backend must not implement locomotion. `step_forward` is refused at the servo layer regardless of safety state.

## Servo Calibration Rules

- Calibration is disabled by default (`"enabled": false` in `config/body.json`).
- Calibration must be explicitly opted into. Do not enable until the servo is physically safe to move.
- Calibration uses narrower test angle ranges than the channel hardware bounds.
- Calibration will not run if hardware libraries are missing — it enters dry-run mode instead.
- Calibration is isolated: it does not connect to the planner, intent parser, safety layer, or body_controller.
- Calibration never includes locomotion actions.
- Re-disable calibration in config after a calibration session.

## Expression Servo Rules

- Servo backend is opt-in. Requires both `"backend": "servo"` and `"servo.enabled": true`.
- Expression actions must use named channels only — no raw channel numbers in action code.
- Angles must stay within per-channel `min_angle`/`max_angle` bounds from config.
- Channels return to home after each expression unless explicitly disabled in motion config.
- Locomotion (`step_forward`) is refused by the servo backend as a second layer of defense.
- Missing hardware libraries trigger dry-run mode, not a crash.

## Status Action Rules

- `report_status` is read-only and must not move hardware.
- It must still pass through the safety layer (present in all mode allowlists).
- It is dispatched directly to `print_status()`, never to the body backend.
- It may expose state and backend information only — no side effects.
