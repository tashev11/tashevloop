import subprocess
import tempfile
import unittest
from pathlib import Path

from tashevloop.autopilot import run_once, select_candidate
from tashevloop.engine import learn
from tashevloop.models import Event
from tashevloop.store import Store


class AutopilotTests(unittest.TestCase):
    def _repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        (root / ".gitignore").write_text(".tashevloop/\n", encoding="utf-8")
        (root / "README.md").write_text("# Demo\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True)

    def test_verified_candidate_merges_and_is_not_retried_without_new_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._repo(project)
            store = Store(project)
            for _ in range(2):
                store.add_event(Event(
                    kind="mistake",
                    title="Missing release guard",
                    description="Release failed because a required guard was absent.",
                    tags=["release"],
                ))
            learn(project)
            self.assertIsNotNone(select_candidate(project))

            def fake_agent(worktree: Path, prompt: str, budget: float) -> dict:
                self.assertIn("Missing release guard", prompt)
                (worktree / "guard.txt").write_text("verified\n", encoding="utf-8")
                return {"returncode": 0, "stdout": "implemented", "stderr": ""}

            result = run_once(
                project,
                test_command="python3 -c \"import pathlib; assert pathlib.Path('guard.txt').exists()\"",
                agent_runner=fake_agent,
                max_budget_usd=0.01,
            )
            self.assertEqual(result["status"], "merged")
            self.assertTrue((project / "guard.txt").exists())

            # The successful attempt adds evidence. That same evidence level must
            # not trigger another paid attempt immediately.
            self.assertIsNone(select_candidate(project))


if __name__ == "__main__":
    unittest.main()
