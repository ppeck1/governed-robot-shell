# Hardware Inventory

## Current (mock only)

No hardware connected. All execution is simulated.

## Planned Hardware Path

| Component               | Purpose                              | Status     |
|-------------------------|--------------------------------------|------------|
| PC or Raspberry Pi      | Runs Python shell                    | TBD        |
| PCA9685 servo driver    | I2C servo signal controller          | Acquired   |
| External servo PSU      | Powers servos (not from PC/Pi)       | TBD        |
| Servos (expression)     | Head yaw, eyelid/flutter, wing       | TBD        |
| Servos (locomotion)     | Legs — Phase 6 only                  | Not yet    |
| Ultrasonic sensor       | Distance — Phase 4                   | Not yet    |
| Bump/touch switch       | Contact sensing — Phase 4            | Not yet    |
| IMU / tilt sensor       | Stability — Phase 4                  | Not yet    |
| Camera                  | Vision — Phase 4+                    | Not yet    |
| Microphone              | Audio input — Phase 5+               | Not yet    |

## Notes

- PCA9685 controls signal only. Common ground with Pi/PC required.
- Servo power must be external and appropriately rated for current draw.
- First real hardware target: one expression servo (head yaw or flutter).
- No leg servos until Phase 6 conditions are met.

## Planned Servo Backend (Phase 3)

- PCA9685 servo driver (I2C)
- External servo power supply (not from Pi/PC)
- Common ground between controller board and servo power rail

### Reserved Expression Channels

| Channel | Name          | Min° | Home° | Max° |
|---------|---------------|------|-------|------|
| 0       | head_yaw      | 60   | 90    | 120  |
| 1       | left_flutter  | 75   | 90    | 105  |
| 2       | right_flutter | 75   | 90    | 105  |

Leg channels not assigned. Locomotion is Phase 6.
