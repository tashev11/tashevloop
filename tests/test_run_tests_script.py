import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_tests.py"


class RunTestsScriptTests(unittest.TestCase):
    """The daemon's verification command must report failures through its exit code."""

    def _checkout(self, root: Path, test_body: str) -> None:
        (root / "scripts").mkdir()
        (root / "src").mkdir()
        (root / "tests").mkdir()
        shutil.copy(SCRIPT, root / "scripts" / "run_tests.py")
        (root / "tests" / "test_sample.py").write_text(
            "import unittest\n\n"
            "class Sample(unittest.TestCase):\n"
            f"    def test_sample(self):\n        {test_body}\n",
            encoding="utf-8",
        )

    def _run(self, root: Path) -> int:
        return subprocess.run(
            [sys.executable, "scripts/run_tests.py"], cwd=root, capture_output=True, text=True, check=False
        ).returncode

    def test_failing_test_gives_non_zero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._checkout(root, "self.fail('boom')")
            self.assertEqual(self._run(root), 1)

    def test_passing_tests_give_zero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._checkout(root, "self.assertTrue(True)")
            self.assertEqual(self._run(root), 0)


if __name__ == "__main__":
    unittest.main()
