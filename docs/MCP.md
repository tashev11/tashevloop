# MCP integration

TashevLoop includes a small stdio MCP server so AI coding agents can use project learning directly.

## Why MCP matters

Without an adapter, a developer has to manually generate context and manually record outcomes.

With MCP, an agent can follow this cycle:

    before task
      → tashevloop_context

    during / after task
      → tashevloop_record

    after meaningful work
      → tashevloop_evolve

    anytime
      → tashevloop_stats

This turns TashevLoop into a shared learning layer instead of another chat history.

## Start server

After installing the package:

    tashevloop-mcp

Or directly from a checkout:

    PYTHONPATH=src python3 -m tashevloop.mcp_server

The server uses the current working directory as the project root.

Set a different project explicitly with:

    TASHEVLOOP_PROJECT=/path/to/project tashevloop-mcp

## Tools

### tashevloop_context

Input:

    {"task":"fix the release pipeline","limit":5}

Returns compact relevant guidance learned from prior evidence.

### tashevloop_record

Input:

    {
      "kind":"fix",
      "title":"Release packaging regression",
      "solution":"Smoke-test the packaged artifact before publishing.",
      "tags":["release","packaging"]
    }

Records evidence and immediately rebuilds lessons.

### tashevloop_evolve

Returns the current improvement proposals generated from repeated failures and unstable project areas.

### tashevloop_stats

Returns memory counts and learning statistics.

## Agent rule

The recommended integration rule is:

1. Call tashevloop_context before making a meaningful change.
2. Work normally.
3. Run the project's verification.
4. Record the outcome.
5. Call tashevloop_evolve when a task closes or a regression is discovered.

This makes the next agent session start smarter than the previous one.
