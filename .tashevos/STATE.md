# State

Updated: 2026-09-23

## Done
- Public repository: https://github.com/tashev11/tashevloop.
- Apache 2.0 license synchronized with GitHub.
- Local-first SQLite evidence store.
- Deterministic lesson builder with confidence/evidence metadata.
- Task-relevant context generation.
- Automatic Git commit ingestion.
- Test pass/fail capture.
- JSONL evidence import with deduplication.
- Adaptive recommendation ranking based on observed project-area reliability.
- Repeated/unresolved failure analysis.
- Automatic IMPROVEMENTS.md and next-task queue.
- Continuous repository watcher.
- Portable background daemon start/stop scripts.
- MCP stdio server for AI agents: context, record, evolve, stats.
- Gated Claude Code autopilot implemented.
- Autopilot uses isolated Git worktrees and branches.
- WebFetch/WebSearch blocked for autopilot.
- Per-attempt budget cap supported.
- Merge only after configured verification passes and main has not moved.
- Failed post-merge verification is reverted.
- Same proposal is not retried until its evidence count increases.
- Local test suite: 12 tests passing.
- Version bumped to 0.2.0.
- GitHub Actions remains manual-only because GitHub reports the owner account is locked due to a billing issue.

## Runtime
- Development Mac has a TashevLoop daemon process configured.
- After this release the daemon must be restarted so it loads the new gated-autopilot code.

## Next
1. Restart daemon with gated autopilot enabled.
2. Add workspace mode to learn across multiple repositories.
3. Add Codex and Gemini native adapters in addition to MCP.
4. Add lesson supersession, stale decay and contradiction handling.
5. Add global cross-project knowledge with private/project boundaries.
6. Add JSONL export and CI adapter.
7. Improve GitHub visual packaging and examples.
