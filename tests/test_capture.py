import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tashevloop.capture import (
    _classify_commit,
    ingest_git,
    ingest_jsonl,
    run_test_command,
)
from tashevloop.store import Store


class CaptureTests(unittest.TestCase):
    def test_commit_classification_matches_whole_words(self):
        cases = {
            "add debug logging": "success",
            "support path prefix": "success",
            "update fixtures": "success",
            "refactor: rename bugs page": "success",
            "неисправность датчика задокументирована": "success",
            "fix: crash on empty cart": "fix",
            "Hotfix release build": "fix",
            "исправил вход": "fix",
            'Revert "add feature"': "warning",
            "откатил миграцию": "warning",
        }
        for subject, kind in cases.items():
            with self.subTest(subject=subject):
                self.assertEqual(_classify_commit(subject), kind)

    def test_git_ingestion_is_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            (project / "app.txt").write_text("ok\n", encoding="utf-8")
            subprocess.run(["git", "add", "app.txt"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "fix release packaging"], cwd=project, check=True, capture_output=True)

            first = ingest_git(project)
            second = ingest_git(project)
            self.assertEqual(first["imported"], 1)
            self.assertEqual(second["imported"], 0)
            self.assertEqual(second["skipped"], 1)
            self.assertEqual(Store(project).stats()["events"], 1)

    def test_test_runner_records_success_and_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            passed = run_test_command(project, [sys.executable, "-c", "print('ok')"])
            failed = run_test_command(project, [sys.executable, "-c", "import sys; sys.exit(3)"])
            self.assertTrue(passed["passed"])
            self.assertFalse(failed["passed"])
            self.assertEqual(failed["returncode"], 3)
            self.assertEqual(Store(project).stats()["events"], 2)

    def test_jsonl_import_is_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source = project / "events.jsonl"
            source.write_text(
                '{"kind":"fix","title":"Known bug","solution":"Keep the fix","tags":["bug"]}\n',
                encoding="utf-8",
            )
            first = ingest_jsonl(project, source)
            second = ingest_jsonl(project, source)
            self.assertEqual(first["imported"], 1)
            self.assertEqual(second["skipped"], 1)

    def test_git_ingestion_drops_commit_trailers(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            messages = [
                "fix login crash\n\nCo-Authored-By: Claude <noreply@anthropic.com>",
                (
                    "add retry budget\n\nRetries stop after three attempts.\n\n"
                    "Signed-off-by: Dev <dev@example.com>\n🤖 Generated with [Claude Code](https://claude.com/claude-code)"
                ),
            ]
            for i, message in enumerate(messages):
                (project / f"file{i}.txt").write_text(f"{i}\n", encoding="utf-8")
                subprocess.run(["git", "add", "."], cwd=project, check=True)
                subprocess.run(["git", "commit", "-m", message], cwd=project, check=True, capture_output=True)

            ingest_git(project)
            events = {e["title"]: e for e in Store(project).events()}
            crash = events["fix login crash"]
            self.assertEqual(crash["description"], "")
            self.assertTrue(crash["solution"].startswith("Preserve the verified fix represented by commit"))
            self.assertEqual(events["add retry budget"]["solution"], "Retries stop after three attempts.")


if __name__ == "__main__":
    unittest.main()
