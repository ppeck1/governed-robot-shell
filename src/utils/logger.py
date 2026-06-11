from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "data" / "logs"
LOG_FILE = LOG_DIR / "robot.log"


def log_event(user_input, intent, action, approved, reason):
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().isoformat(timespec="seconds")

    line = (
        f"{timestamp} | "
        f"input={user_input!r} | "
        f"intent={intent} | "
        f"action={action} | "
        f"approved={approved} | "
        f"reason={reason}\n"
    )

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line)
