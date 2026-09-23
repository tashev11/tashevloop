import tempfile
import unittest
from pathlib import Path

from tashevloop import __version__
from tashevloop.mcp_server import call_tool, handle_request


class MCPTests(unittest.TestCase):
    def test_initialize_and_tool_list(self):
        init = handle_request({"jsonrpc":"2.0","id":1,"method":"initialize"}, Path("."))
        self.assertEqual(init["result"]["serverInfo"]["name"], "tashevloop")
        self.assertEqual(init["result"]["serverInfo"]["version"], __version__)
        tools = handle_request({"jsonrpc":"2.0","id":2,"method":"tools/list"}, Path("."))
        names = {item["name"] for item in tools["result"]["tools"]}
        self.assertIn("tashevloop_context", names)
        self.assertIn("tashevloop_record", names)

    def test_agent_can_record_and_read_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            result = call_tool("tashevloop_record", {
                "kind":"fix",
                "title":"Always verify packaged desktop artifact",
                "solution":"Smoke-test the packaged artifact before publishing.",
                "tags":["release","packaging"],
            }, project)
            self.assertIn("Recorded event", result["content"][0]["text"])

            context = call_tool("tashevloop_context", {
                "task":"prepare release packaging",
                "limit":5,
            }, project)
            text = context["content"][0]["text"]
            self.assertIn("Smoke-test", text)

    def test_evolve_tool_returns_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            result = call_tool("tashevloop_evolve", {}, project)
            self.assertTrue(result["content"])
            self.assertEqual(result["content"][0]["type"], "text")


if __name__ == "__main__":
    unittest.main()
