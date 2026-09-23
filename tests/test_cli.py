import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

from tashevloop.cli import main
from tashevloop.store import Store


class CLITests(unittest.TestCase):
    def test_watch_autopilot_requires_test_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as raised:
                main(["--project", tmp, "watch", "--autopilot", "--once"])
            self.assertEqual(raised.exception.code, 2)
            self.assertIn("--test-command", err.getvalue())

    def test_init_keeps_the_store_out_of_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            (project / "app.txt").write_text("ok\n", encoding="utf-8")
            subprocess.run(["git", "add", "app.txt"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=project, check=True, capture_output=True)

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--project", tmp, "init"]), 0)
            self.assertEqual((Store(project).home / ".gitignore").read_text(encoding="utf-8"), "*\n")
            status = subprocess.run(
                ["git", "status", "--porcelain"], cwd=project, check=True, capture_output=True, text=True
            ).stdout
            self.assertEqual(status, "")

            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(["--project", tmp, "doctor"]), 0)
            self.assertIn("status: OK", out.getvalue())

    def test_doctor_warns_outside_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(["--project", tmp, "doctor"]), 0)
            self.assertIn("not a Git repository", out.getvalue())
            self.assertIn("status: 1 warning(s)", out.getvalue())


if __name__ == "__main__":
    unittest.main()
