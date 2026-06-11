from interface.cli import get_user_input
from brain.state import RobotState
from body.body_controller import BodyController
from runtime import RobotRuntime


def print_status(state: RobotState, body: BodyController) -> None:
    """Print a read-only snapshot of current session state. Does not move hardware."""
    body_status = body.get_status()
    positions = body_status.get("servo_positions", {})

    print("\n[STATUS]")
    print(f"  mode              : {state.mode}")
    print(f"  movement_enabled  : {state.movement_enabled}")
    print(f"  last_intent       : {state.last_intent}")
    print(f"  last_action       : {state.last_action}")
    print(f"  backend           : {body_status['backend']}")
    print(f"  servo_enabled     : {body_status['servo_enabled']}")
    print(f"  servo_ready       : {body_status['servo_ready']}")
    if positions:
        print("  servo_positions   :")
        for ch, angle in positions.items():
            print(f"    {ch:<20} {angle:.1f} deg")
    else:
        print("  servo_positions   : {}")

    sim_snapshot = body_status.get("sim") or {}
    if sim_snapshot:
        robot = sim_snapshot.get("robot", {})
        sensors = sim_snapshot.get("sensors", {})
        pose = robot.get("pose", {})
        print(
            "  sim_pose          : "
            f"x={pose.get('x')} z={pose.get('z')} heading={pose.get('heading_degrees')}"
        )
        print(f"  sim_expression    : {robot.get('expression')}")
        print(f"  sim_front_clearance: {sensors.get('front_clearance')}")


def main():
    print("LLM Robot Shell Online")
    print("Mode: shell | Movement: disabled\n")

    runtime = RobotRuntime(state=RobotState(), body=BodyController())
    state = runtime.state
    body = runtime.body

    while True:
        user_input = get_user_input()

        if user_input == "quit":
            print("Shutting down.")
            break

        event = runtime.process_command(user_input, source="cli")
        action = event["action"]
        approved = event["approved"]
        reason = event["reason"]

        if approved:
            if action == "report_status":
                print_status(state, body)
        else:
            print(f"\n[SAFETY BLOCK] {reason}")


if __name__ == "__main__":
    main()
