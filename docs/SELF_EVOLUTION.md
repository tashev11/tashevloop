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

Source-code self-improvement should use a gated loop:

    proposal
       ↓
    isolated branch/worktree
       ↓
    AI or deterministic implementation
       ↓
    tests / checks
       ↓
    accept only verified improvement
       ↓
    record outcome as evidence

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

The daemon only runs verification after repository changes, so an idle repository does not continuously burn CPU or model tokens.
