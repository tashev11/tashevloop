from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from .engine import context_markdown, learn
from .evolution import build_improvement_plan
from .models import Event, VALID_KINDS
from .store import Store


PROTOCOL_VERSION = "2025-06-18"


def project_root() -> Path:
    return Path(os.environ.get("TASHEVLOOP_PROJECT", ".")).expanduser().resolve()


def tool_catalog() -> list[dict[str, Any]]:
    return [
        {
            "name": "tashevloop_context",
            "description": "Get compact project-learned guidance relevant to the current coding task.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                },
                "required": ["task"],
            },
        },
        {
            "name": "tashevloop_record",
            "description": "Record a mistake, fix, success, decision or warning as project evidence.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": sorted(VALID_KINDS)},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "solution": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["kind", "title"],
            },
        },
        {
            "name": "tashevloop_evolve",
            "description": "Analyze accumulated evidence and return high-signal next improvement proposals.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "tashevloop_stats",
            "description": "Return current TashevLoop memory and learning statistics.",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


def _text_result(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def call_tool(name: str, arguments: dict[str, Any], project: Path | None = None) -> dict:
    root = (project or project_root()).resolve()
    store = Store(root)

    if name == "tashevloop_context":
        task = str(arguments.get("task", "")).strip()
        if not task:
            raise ValueError("task is required")
        limit = max(1, min(20, int(arguments.get("limit", 5))))
        return _text_result(context_markdown(root, task, limit))

    if name == "tashevloop_record":
        kind = str(arguments.get("kind", "")).strip()
        title = str(arguments.get("title", "")).strip()
        tags = arguments.get("tags") or []
        event_id = store.add_event(Event(
            kind=kind,
            title=title,
            description=str(arguments.get("description", "")),
            solution=str(arguments.get("solution", "")),
            tags=[str(x) for x in tags],
            source="mcp",
        ))
        lessons = learn(root)
        return _text_result(
            f"Recorded event #{event_id}. TashevLoop now has {len(lessons)} learned lesson(s)."
        )

    if name == "tashevloop_evolve":
        proposals = build_improvement_plan(root)
        if not proposals:
            return _text_result("No high-signal improvement proposals yet.")
        lines = [f"{len(proposals)} improvement proposal(s):"]
        for item in proposals[:10]:
            lines.append(
                f"- [{item['priority']}] {item['title']}: {item['action']} "
                f"(reason: {item['reason']})"
            )
        return _text_result("\n".join(lines))

    if name == "tashevloop_stats":
        return _text_result(json.dumps(store.stats(), ensure_ascii=False, indent=2))

    raise ValueError(f"unknown tool: {name}")


def handle_request(request: dict[str, Any], project: Path | None = None) -> dict | None:
    method = request.get("method")
    request_id = request.get("id")

    if method == "notifications/initialized":
        return None

    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "tashevloop", "version": "0.1.0"},
        }
    elif method == "tools/list":
        result = {"tools": tool_catalog()}
    elif method == "tools/call":
        params = request.get("params") or {}
        result = call_tool(
            str(params.get("name", "")),
            params.get("arguments") or {},
            project=project,
        )
    elif method == "ping":
        result = {}
    else:
        if request_id is None:
            return None
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    if request_id is None:
        return None
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            request_id = None
            try:
                request_id = request.get("id")  # type: ignore[name-defined]
            except Exception:
                pass
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": str(exc)},
            }
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
