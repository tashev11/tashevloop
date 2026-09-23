# Architecture

TashevLoop separates raw evidence from derived guidance.

    Event sources
      ├─ human
      ├─ AI agent
      ├─ git
      ├─ tests
      └─ CI
          ↓
    Local event store (SQLite)
          ↓
    Deterministic lesson builder
          ↓
    Lesson store
          ↓
    Task relevance ranking
          ↓
    Compact context / adapter

## Principles

1. Evidence first: a lesson must point back to recorded outcomes.
2. Local first: core operation does not require a cloud account.
3. Vendor neutral: project learning must survive switching AI tools.
4. Compact by default: retrieval should reduce context, not grow it.
5. Uncertainty is visible: confidence is metadata, not marketing.
6. Human-overridable: derived lessons can be inspected and replaced in future versions.

## v0.1 boundaries

The first release uses lexical similarity and deterministic confidence. It does not call an LLM and does not claim semantic understanding. Optional semantic ranking is planned as a replaceable layer.
