# Contributing

Keep this example small, reproducible, and safe to run without provider credentials.

## Setup and offline checks

Use Python 3.11+ and uv. Linux/Python 3.12 is the verified environment; interactive review requires a POSIX terminal.

```bash
uv sync --locked --group dev
uv run --offline pytest -q
uv run --offline ruff check src tests
uv run --offline ruff format --check src tests
uv run --offline python -m compileall -q src
```

The initial sync downloads open-source packages from PyPI. Do not add a paid API, live-provider requirement, telemetry, credentials, or automatic publishing to the default workflow.

Use `uv run --offline ruff format src tests` to format changes. Add regression tests before behavior changes and run the full suite after focused checks. Do not hide upstream warnings or raise timeouts merely to conceal hangs. Include Python and dependency versions with reproducible failures.

The suite exercises actual MCP stdio and mcp-agent human input. Tests must remain independent of API keys, GitHub sign-in, live repositories, and hosted services. Injected approvals and pseudo-terminal inputs must be labeled scripted tests, never actual human review. Preserve cancellation, timeout cleanup, stale-draft, injection, resolved-path, and exclusive-write tests.

## Fixtures

`examples/changes.json` is fictional. Never replace it with private source data or secrets. Draft artifacts embed the complete normalized source, including PR bodies.

```bash
mkdir -p out
uv run --offline release-notes draft \
  --input examples/changes.json --output out/candidate-draft.json
uv run --offline release-notes inspect out/candidate-draft.json
```

For an intended generator change, review the candidate diff and update `examples/draft.json` and `examples/draft-preview.txt` together. Update the verification record's digest. Explain schema, normalization, label, or generator-identifier changes. Do not patch a hash merely to pass a test.

## Documentation and packaging

Keep the README, article, security boundaries, and verification record consistent with the code. Document limits instead of overstating security. The single-user gate does not authenticate anyone or authorize external publication.

```bash
uv build --offline
```

Build dependencies must already be cached; otherwise install them from the official registry first. Verify that the sdist contains this guide, README, tests, fixtures, security notes, licenses, and the verification record. Test the wheel in a fresh environment when changing entry points or packaging. Do not include environments, caches, local notes, generated exports, or credentials in contributions.

A proposed change should state the behavior changed, reproduction if applicable, exact checks/results, and remaining limits.

## Security reports

Read [SECURITY.md](SECURITY.md). Public issues should use fictional data and omit sensitive exploitation details. Use private vulnerability reporting if the published repository offers it; otherwise ask the maintainer for a private channel without posting sensitive details. Never disclose credentials or confidential PR content in a public issue.
