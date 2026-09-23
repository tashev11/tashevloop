<p align="center">
  <h1 align="center">TashevLoop</h1>
  <p align="center"><strong>Your AI coding stack should stop making the same mistake twice.</strong></p>
</p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Local first" src="https://img.shields.io/badge/local--first-no%20cloud-111827">
  <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-16a34a">
  <img alt="Stage alpha" src="https://img.shields.io/badge/stage-alpha-f59e0b">
</p>

## What it is

TashevLoop is an open-source learning layer for AI-assisted development.

Codex, Claude, Gemini, ChatGPT, IDE agents and humans all make useful discoveries during a project. Most of those discoveries disappear into old chats and terminal history. TashevLoop turns them into a small local reusable memory:

**mistake → fix → lesson → relevant context → better next attempt**

The core is local-first, tool-agnostic and has no model API dependency.

## The pain it solves

- agents repeat bugs already fixed in another chat;
- every new AI session burns tokens rediscovering project history;
- useful decisions are buried in transcripts;
- memory grows forever instead of becoming sharper;
- different AI tools do not share the same operational lessons;
- vibe-coded projects move fast, but their process rarely gets smarter.

## 60-second start

    git clone https://github.com/tashev11/tashevloop.git
    cd tashevloop
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .
    tashevloop init

Record what happened:

    tashevloop record --kind mistake --title "Desktop build missed runtime data" --description "App crashed after packaging" --tags electron,release

    tashevloop record --kind fix --title "Desktop build missed runtime data" --solution "Smoke-test the packaged artifact and verify build.files before publishing." --tags electron,release

    tashevloop learn
    tashevloop suggest "prepare the next Electron release"

Generate a compact context file for any AI:

    tashevloop context "fix the Electron release pipeline" --output .tashevloop/CONTEXT.md

Then point Codex, Claude, Gemini, Cursor, Windsurf, Copilot or another agent at that file.

## Commands

| Command | Purpose |
|---|---|
| tashevloop init | create local project memory |
| tashevloop record | save a mistake, fix, success, decision or warning |
| tashevloop learn | turn evidence into reusable lessons |
| tashevloop suggest | rank lessons for the next task |
| tashevloop context | generate compact AI-ready Markdown |
| tashevloop stats | inspect memory size |
| tashevloop doctor | verify local setup |

## Learning model

TashevLoop v0.1 intentionally starts deterministic. It does not pretend that one old event is universal truth.

Every lesson has evidence count, failure count, verified success/fix count, confidence, tags, a compact signature and the latest proven guidance.

## Designed for multiple AIs

    Codex ─┐
    Claude ├──> TashevLoop evidence ──> learned context ──> next task
    Gemini ┤
    Cursor ┤
    Human ─┘

Adapters and automatic session ingestion are on the roadmap. The data model is neutral so no AI vendor owns the project memory.

## Why this is different from chat memory

Chat memory answers: **what happened before?**

TashevLoop aims to answer: **what did we learn that changes what we should do now?**

That distinction is the product.

## Privacy

The local database lives inside the project at .tashevloop/memory.db and is gitignored by default. v0.1 sends nothing to a TashevLoop server.

## Attribution

TashevLoop is open source under the MIT License.

Project identity:

**TashevLoop by Rinat Tashev — github.com/tashev11/tashevloop**

The MIT copyright/license notice must remain in copies or substantial portions of the software.

## Roadmap

See ROADMAP.md. Near-term work includes automatic Git and CI event ingestion, adapters for leading AI tools, regression-aware lessons, team synchronization and optional semantic ranking.

## Contributing

Issues and pull requests are welcome. Please read CONTRIBUTING.md.

---

<p align="center">
  <strong>TashevLoop</strong><br>
  Make every AI coding cycle teach the next one.<br><br>
  MIT © Rinat Tashev
</p>
