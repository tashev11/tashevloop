from __future__ import annotations

import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tashevloop.daemon import watch  # noqa: E402


if __name__ == "__main__":
    # run_tests.py tests the checkout it lives in and exits non-zero on failure,
    # so the same command is valid here and inside autopilot worktrees.
    test_command = f"{shlex.quote(sys.executable)} scripts/run_tests.py"
    watch(
        ROOT,
        interval=60,
        test_command=test_command,
        autopilot=True,
        max_budget_usd=0.75,
    )
