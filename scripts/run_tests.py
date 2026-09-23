"""Run this checkout's test suite against its own src/ and exit non-zero on failure.

The daemon uses it both in the repository and inside autopilot worktrees, so
the result always describes the code in the directory the script lives in.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
result = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
