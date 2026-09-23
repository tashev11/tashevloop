import tempfile
import unittest
from pathlib import Path

from tashevloop.engine import context_markdown, learn, suggest
from tashevloop.models import Event
from tashevloop.store import Store


class EngineTests(unittest.TestCase):
    def test_mistake_and_fix_become_reusable_lesson(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            store = Store(project)
            store.add_event(Event(
                kind="mistake",
                title="Forgot to include cities.js in Electron build",
                description="Packaged desktop app crashed after release",
                tags=["electron", "release", "build"],
            ))
            store.add_event(Event(
                kind="fix",
                title="Forgot to include cities.js in Electron build",
                description="Added the missing file to build.files and rebuilt",
                solution="Before Electron release, verify every runtime data file is included in build.files.",
                tags=["electron", "release", "build"],
            ))

            lessons = learn(project)
            self.assertEqual(len(lessons), 1)
            self.assertEqual(lessons[0].success_count, 1)
            self.assertIn("build.files", lessons[0].guidance)

            tips = suggest(project, "release electron build package", limit=3)
            self.assertTrue(tips)
            self.assertGreater(tips[0]["confidence"], 0.3)

    def test_context_is_compact_and_human_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            store = Store(project)
            store.add_event(Event(
                kind="decision",
                title="Read project state before editing",
                description="Always read STATE.md and project guardrails before changing code.",
                tags=["context", "agents"],
            ))
            learn(project)
            text = context_markdown(project, "agent context before coding")
            self.assertIn("# TashevLoop Context", text)
            self.assertIn("STATE.md", text)


if __name__ == "__main__":
    unittest.main()
