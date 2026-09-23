# Self-evolution model

TashevLoop is designed to improve continuously without blindly rewriting its own source.

## Continuous loop

1. Watch the repository for a new Git HEAD.
2. Import new commits as evidence.
3. Run the configured verification command.
4. Record pass/fail as new evidence.
5. Rebuild lessons.
6. Recalculate tag reliability.
7. Re-rank future guidance.
8. Detect repeated and unresolved failures.
9. Write a concrete improvement plan to .tashevloop/IMPROVEMENTS.md.
10. Repeat.

## What changes automatically

- evidence database;
- lesson confidence;
- area reliability;
- recommendation ranking;
- improvement priorities;
- next-task queue;
- context generated for AI agents.

## What does not change blindly

TashevLoop does not directly rewrite production source simply because an inferred lesson says so.

Source-code self-improvement uses a gated loop:

    proposal
       ↓
    isolated branch/worktree
       ↓
    Claude Code bounded implementation (files only: no commands, no web)
       ↓
    tamper check: existing tests, runner scripts, CI, LICENSE untouched
       ↓
    verification command inside the worktree
       ↓
    fast-forward the checkout only if it is clean and main did not move
       ↓
    record outcome as evidence

The default Claude runner allows only Read, Edit, Write, Glob and Grep and disables Bash, WebFetch and WebSearch. It limits the task scope and applies a per-attempt budget cap. The merge commit is built from the already verified tree, so nothing is verified or reverted in your checkout. If the checkout moved or has uncommitted changes, the verified branch is kept instead.

TashevLoop remembers the evidence level of each attempt, including attempts that time out or fail to start, so the same unresolved signal cannot trigger repeated paid attempts without new evidence.

The tamper check keeps the agent from weakening the gate that judges it. It is not a sandbox: verification runs code the agent wrote, with your user permissions.

This keeps the system capable of learning continuously while avoiding irreversible self-corruption.

## Continuous process

For this repository:

    python3 scripts/start_daemon.py

Status is written to:

    .tashevloop/daemon-status.json

Generated improvement plan:

    .tashevloop/IMPROVEMENTS.md

Stop:

    python3 scripts/stop_daemon.py

The daemon only runs verification after repository changes, so an idle repository does not continuously burn CPU or model tokens. After a failed cycle it still records the HEAD it saw, so an error does not turn into a retry every interval.
