# State

Updated: 2026-09-24

## Done
- Public repository: https://github.com/tashev11/tashevloop.
- Apache 2.0 license synchronized with GitHub.
- Local-first SQLite evidence store; `init` writes `.tashevloop/.gitignore` so the store never enters Git history.
- Deterministic lesson builder with confidence/evidence metadata.
- Task-relevant context generation.
- Automatic Git commit ingestion; commits are classified by whole words.
- Test pass/fail capture.
- JSONL evidence import with deduplication.
- Adaptive recommendation ranking based on observed project-area reliability.
- Repeated/unresolved failure analysis.
- Automatic IMPROVEMENTS.md and next-task queue.
- Continuous repository watcher; a failed cycle records the HEAD it saw and is not repeated until HEAD changes.
- Portable background daemon start/stop scripts; the daemon verifies with `scripts/run_tests.py`, which exits non-zero on failure.
- MCP stdio server for AI agents: context, record, evolve, stats.
- Gated Claude Code autopilot:
  - requires a verification command (`watch --autopilot` refuses to start without one);
  - the agent works in an isolated Git worktree and branch with Read, Edit, Write, Glob and Grep only; Bash, WebFetch and WebSearch are disabled;
  - candidates that modify or delete existing tests, add discovery hooks, or touch LICENSE, NOTICE, `.github/` or the runner scripts are rejected;
  - verification runs in the worktree; the checkout is only fast-forwarded to a verified merge commit while it is clean and main has not moved, otherwise the verified branch is kept;
  - timeouts and runner failures count as attempts; the same proposal is not retried until its evidence count increases;
  - per-attempt budget cap.
- Local test suite: 25 tests passing.
- Version 0.2.1.
- GitHub Actions is manual-only for now.

## Runtime
- The daemon is started with `python3 scripts/start_daemon.py` and runs the gated autopilot.
- Restart it after pulling new code so it loads the update.

## Next
1. Add workspace mode to learn across multiple repositories.
2. Add Codex and Gemini native adapters in addition to MCP.
3. Add lesson supersession, stale decay and contradiction handling.
4. Add global cross-project knowledge with private/project boundaries.
5. Add JSONL export and CI adapter.
6. Improve GitHub visual packaging and examples.
