import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tashevloop.daemon import cycle, watch
from tashevloop.engine import learn, suggest
from tashevloop.evolution import build_improvement_plan
from tashevloop.models import Event
from tashevloop.store import Store


class EvolutionTests(unittest.TestCase):
    def test_repeated_failures_generate_improvement_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            store = Store(project)
            for _ in range(2):
                store.add_event(Event(
                    kind="mistake",
                    title="Release misses generated assets",
                    description="Packaged application fails",
                    tags=["release", "packaging"],
                ))
            learn(project)
            proposals = build_improvement_plan(project)
            self.assertTrue(any(x["kind"] == "repeated-failure" for x in proposals))
            self.assertTrue((project / ".tashevloop" / "IMPROVEMENTS.md").exists())

    def test_ranking_uses_area_reliability(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            store = Store(project)
            store.add_event(Event(
                kind="fix",
                title="Verified deployment preflight",
                solution="Run the preflight before deploy.",
                tags=["deploy"],
            ))
            learn(project)
            rows = suggest(project, "deploy preflight")
            self.assertTrue(rows)
            self.assertIn("area_reliability", rows[0])

    def test_daemon_cycle_imports_new_git_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            (project / "app.txt").write_text("ok\n", encoding="utf-8")
            subprocess.run(["git", "add", "app.txt"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "fix startup regression"], cwd=project, check=True, capture_output=True)

            result = cycle(project, force=True)
            self.assertTrue(result["changed"])
            self.assertEqual(result["git_imported"], 1)
            self.assertGreaterEqual(result["lessons"], 1)
            self.assertTrue((project / ".tashevloop" / "daemon-status.json").exists())

    def test_failed_cycle_is_not_repeated_while_head_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            (project / "app.txt").write_text("ok\n", encoding="utf-8")
            subprocess.run(["git", "add", "app.txt"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=project, check=True, capture_output=True)
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=project, check=True, capture_output=True, text=True
            ).stdout.strip()

            calls = []

            def missing_test_binary(project_path, command):
                calls.append(command)
                raise FileNotFoundError(command[0])

            # Three cycles with an unchanged HEAD; the third sleep ends the loop.
            with (
                mock.patch("tashevloop.daemon.run_test_command", side_effect=missing_test_binary),
                mock.patch("tashevloop.daemon.time.sleep", side_effect=[None, None, KeyboardInterrupt]),
                self.assertRaises(KeyboardInterrupt),
            ):
                watch(project, interval=60, test_command="missing-test-binary")

            self.assertEqual(len(calls), 1)
            status = json.loads((project / ".tashevloop" / "daemon-status.json").read_text(encoding="utf-8"))
            self.assertIn("error", status)
            self.assertEqual(status["head"], head)


if __name__ == "__main__":
    unittest.main()
