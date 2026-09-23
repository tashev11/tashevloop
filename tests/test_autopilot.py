import subprocess
import tempfile
import unittest
from pathlib import Path

from tashevloop.autopilot import run_once, select_candidate
from tashevloop.engine import learn
from tashevloop.models import Event
from tashevloop.store import Store

PASS = "python3 -c pass"
FAIL = 'python3 -c "raise SystemExit(1)"'


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


class AutopilotTests(unittest.TestCase):
    def _repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        (root / ".gitignore").write_text(".tashevloop/\n", encoding="utf-8")
        (root / "README.md").write_text("# Demo\n", encoding="utf-8")
        (root / "tests").mkdir()
        (root / "tests" / "test_existing.py").write_text("# existing test\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True)

    def _project(self, tmp: str) -> Path:
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
        return project

    def _leftovers(self, project: Path) -> tuple[list[str], list[str]]:
        worktrees = [
            line for line in _git(project, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ") and "-auto-" in line
        ]
        branches = _git(project, "branch", "--list", "tashevloop/*", "--format=%(refname:short)").split()
        return worktrees, branches

    def test_verified_candidate_fast_forwards_a_clean_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(tmp)
            base = _git(project, "rev-parse", "HEAD")

            def fake_agent(worktree: Path, prompt: str, budget: float) -> dict:
                self.assertIn("Missing release guard", prompt)
                (worktree / "guard.txt").write_text("verified\n", encoding="utf-8")
                (worktree / "tests" / "test_guard.py").write_text("# new test\n", encoding="utf-8")
                return {"returncode": 0, "stdout": "implemented", "stderr": ""}

            result = run_once(
                project,
                test_command="python3 -c \"import pathlib; assert pathlib.Path('guard.txt').exists()\"",
                agent_runner=fake_agent,
                max_budget_usd=0.01,
            )
            self.assertEqual(result["status"], "merged")
            self.assertTrue((project / "guard.txt").exists())

            # A merge commit on top of the base, and nothing left uncommitted.
            parents = _git(project, "rev-list", "--parents", "-n", "1", "HEAD").split()
            self.assertEqual(len(parents), 3)
            self.assertEqual(parents[1], base)
            self.assertEqual(_git(project, "status", "--porcelain"), "")
            self.assertEqual(self._leftovers(project), ([], []))

            # The successful attempt adds evidence. That same evidence level must
            # not trigger another paid attempt immediately.
            self.assertIsNone(select_candidate(project))

    def test_autopilot_requires_a_verification_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(tmp)
            base = _git(project, "rev-parse", "HEAD")
            calls = []

            def fake_agent(worktree: Path, prompt: str, budget: float) -> dict:
                calls.append(worktree)
                return {"returncode": 0, "stdout": "", "stderr": ""}

            result = run_once(project, test_command="  ", agent_runner=fake_agent)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(calls, [])
            self.assertEqual(_git(project, "rev-parse", "HEAD"), base)

    def test_failed_verification_leaves_the_checkout_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(tmp)
            base = _git(project, "rev-parse", "HEAD")

            def fake_agent(worktree: Path, prompt: str, budget: float) -> dict:
                (worktree / "broken.txt").write_text("broken\n", encoding="utf-8")
                return {"returncode": 0, "stdout": "", "stderr": ""}

            result = run_once(project, test_command=FAIL, agent_runner=fake_agent)
            self.assertEqual(result["status"], "verification-failed")
            self.assertEqual(_git(project, "rev-parse", "HEAD"), base)
            self.assertFalse((project / "broken.txt").exists())
            self.assertEqual(self._leftovers(project), ([], []))

    def test_agent_error_counts_as_an_attempt_and_is_cleaned_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(tmp)

            def hanging_agent(worktree: Path, prompt: str, budget: float) -> dict:
                raise subprocess.TimeoutExpired(cmd="claude", timeout=1800)

            result = run_once(project, test_command=PASS, agent_runner=hanging_agent)
            self.assertEqual(result["status"], "agent-error")
            self.assertIn("TimeoutExpired", result["detail"])
            self.assertEqual(self._leftovers(project), ([], []))
            # Without new evidence the same proposal must not start another paid run.
            self.assertIsNone(select_candidate(project))

    def test_candidate_may_not_change_existing_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(tmp)
            base = _git(project, "rev-parse", "HEAD")

            def weakening_agent(worktree: Path, prompt: str, budget: float) -> dict:
                (worktree / "tests" / "test_existing.py").write_text("# disabled\n", encoding="utf-8")
                (worktree / "guard.txt").write_text("verified\n", encoding="utf-8")
                return {"returncode": 0, "stdout": "", "stderr": ""}

            result = run_once(project, test_command=PASS, agent_runner=weakening_agent)
            self.assertEqual(result["status"], "protected-change")
            self.assertIn("tests/test_existing.py", result["detail"])
            self.assertEqual(_git(project, "rev-parse", "HEAD"), base)
            self.assertEqual(self._leftovers(project), ([], []))

    def test_uncommitted_work_in_the_checkout_keeps_the_verified_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(tmp)
            base = _git(project, "rev-parse", "HEAD")

            def agent_while_developer_edits(worktree: Path, prompt: str, budget: float) -> dict:
                (worktree / "guard.txt").write_text("verified\n", encoding="utf-8")
                (project / "notes.txt").write_text("work in progress\n", encoding="utf-8")
                return {"returncode": 0, "stdout": "", "stderr": ""}

            result = run_once(project, test_command=PASS, agent_runner=agent_while_developer_edits)
            self.assertEqual(result["status"], "main-dirty")
            self.assertEqual(_git(project, "rev-parse", "HEAD"), base)
            self.assertEqual((project / "notes.txt").read_text(encoding="utf-8"), "work in progress\n")
            worktrees, branches = self._leftovers(project)
            self.assertEqual(worktrees, [])
            self.assertEqual(branches, [result["branch"]])

    def test_moved_main_keeps_the_verified_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(tmp)

            def agent_while_developer_commits(worktree: Path, prompt: str, budget: float) -> dict:
                (worktree / "guard.txt").write_text("verified\n", encoding="utf-8")
                (project / "other.txt").write_text("other\n", encoding="utf-8")
                subprocess.run(["git", "add", "other.txt"], cwd=project, check=True)
                subprocess.run(["git", "commit", "-m", "developer commit"], cwd=project, check=True, capture_output=True)
                return {"returncode": 0, "stdout": "", "stderr": ""}

            result = run_once(project, test_command=PASS, agent_runner=agent_while_developer_commits)
            self.assertEqual(result["status"], "main-moved")
            self.assertEqual(_git(project, "log", "-1", "--format=%s"), "developer commit")
            self.assertFalse((project / "guard.txt").exists())
            self.assertEqual(self._leftovers(project)[1], [result["branch"]])


if __name__ == "__main__":
    unittest.main()
