from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tashevloop.daemon import watch  # noqa: E402


if __name__ == "__main__":
    test_command = (
        "python3 -c "
        "\"__import__('sys').path.insert(0,'src') or "
        "__import__('unittest').TextTestRunner(verbosity=1).run("
        "__import__('unittest').defaultTestLoader.discover('tests'))\""
    )
    watch(ROOT, interval=60, test_command=test_command)
