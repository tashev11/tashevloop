# Contributing

Thanks for improving TashevLoop.

1. Open an issue for significant behavior changes.
2. Keep the core local-first and vendor-neutral.
3. Add tests for new learning behavior.
4. Never introduce silent collection or upload of project source/history.
5. Prefer explainable evidence over opaque scoring.

Development:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .
    python -m unittest discover -s tests -p "test_*.py"

By contributing, you agree that your contribution is licensed under the repository Apache License 2.0.
