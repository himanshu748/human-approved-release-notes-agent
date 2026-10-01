# Human-Approved Release Notes Agent

Turn a local PR export into a traceable release-note draft. Review the exact content, then explicitly approve a local Markdown export.

**No API key. No LLM calls. No cloud service.** This is a deterministic, runnable example of **mcp-agent's real tool and human-input integration**, with a deliberately small permission boundary.

The included `example/harbor` repository and all sample PRs are fictional. Sample outputs are generated from those fixtures, not from a real repository or a model. No example is presented as a human-approved release.

## Quick start

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/). Interactive review uses a POSIX terminal (Linux/macOS). The freshly verified development environment is Linux, Python 3.12.

```bash
uv sync --locked
mkdir -p out
uv run --offline release-notes draft \
  --input examples/changes.json --output out/draft.json
uv run --offline release-notes inspect out/draft.json
uv run --offline release-notes review out/draft.json \
  --output out/RELEASE_NOTES.md --reviewer your-handle
```

The first command downloads ordinary open-source dependencies from PyPI. After installation, the workflow commands run locally with no provider or remote service. `uv --offline` prevents uv from downloading; application behavior is verified separately by network-tripwire tests.

The review command displays the notes, warnings, skipped PRs, full digest, and destination. Read them, then type the displayed `APPROVE <full-digest>` phrase. Anything else declines. Piped input is rejected; there is no `--yes` flag. Approval covers only the specified local file. Nothing is published to GitHub.

All outputs are created exclusively. If you repeat a command, choose a new output filename rather than overwriting a prior draft or release.

To inspect without installing the framework, read [the committed draft preview](examples/draft-preview.txt) or [the original source fixture](examples/changes.json).

## What it does

1. Validates a size-bounded local PR snapshot
2. Starts a local FastMCP stdio server exposing one read-only tool: `list_changes`
3. Uses `MCPApp`, `Agent.list_tools`, and `Agent.call_tool` to retrieve the snapshot
4. Groups merged PR titles under breaking changes, features, fixes, documentation, or maintenance
5. Stores the normalized source, its SHA-256, deterministic Markdown, warnings, and draft digest in one JSON artifact
6. Uses `Agent.request_human_input` and `HumanInputRequest` for explicit review
7. Re-reads and checks the draft, then exclusively creates the approved local export

The review agent has no external servers. No publish, shell, arbitrary-file-read, or GitHub-write tool is exposed. The export code is outside the agent's tool registry.

### Why deterministic?

A reference implementation should let a reader reproduce its evidence and test the review boundary without buying API access. Here, PR titles and labels drive a transparent template. Bodies are retained for provenance and scanned for a few instruction-like phrases; they never become commands or model instructions.

This mode does **not** summarize implementation details, infer user benefits, or invent migration instructions. A breaking-change label adds a migration-guidance reminder. A maintainer still needs to write and verify the final externally published release notes.

## Input format

```json
{
  "repository": "example/harbor",
  "version": "v1.4.0",
  "pull_requests": [
    {
      "number": 41,
      "title": "Add CSV export for filtered results",
      "body": "Exports the selected columns.",
      "labels": ["feature"],
      "url": "https://github.com/example/harbor/pull/41",
      "merged": true
    }
  ]
}
```

`body` and `labels` may be omitted. All other shown fields are required. Unknown fields, duplicate PR numbers, type coercion, noncanonical URLs, and hidden control characters are rejected. PRs are sorted numerically and labels are normalized. Limits: 1 MiB source JSON, 500 PRs, 500-character titles, 20,000-character bodies, and 50 labels per PR.

For your own repository, export the relevant PRs with your usual read-only GitHub workflow and convert them into this schema. The application accepts no credentials and does not fetch GitHub data. Choose the release range yourself: it does not verify branches, tags, merge dates, or snapshot completeness. Hashes establish local consistency, not GitHub authenticity.

Label precedence is breaking change → feature → fix → documentation → maintenance. Aliases are listed in [`core.py`](src/release_notes_agent/core.py). Unmerged PRs remain in provenance but are excluded from note entries.

## Review the evidence

```bash
uv run --offline release-notes inspect out/draft.json --sources
```

This also prints normalized source JSON. Treat every title and body as untrusted. The warning heuristic is intentionally narrow; absence of a warning says nothing about trustworthiness.

Draft JSON is machine-generated and integrity-checked. Editing its Markdown directly invalidates it. Regenerate from the intended snapshot for another review. Any editorial changes after export need their own review before external publication; an old digest does not cover later edits.

## Tests

```bash
uv sync --locked --group dev
uv run --offline pytest -q
uv run --offline ruff check src tests
uv run --offline ruff format --check src tests
```

Tests cover validation, stable ordering and hashes, source provenance, escaping, stale/tampered drafts, rejection, callback errors, cancellation, timeouts, output conflicts, resolved-path validation, actual MCP stdio, and actual mcp-agent human input. Pseudo-terminal tests exercise the interactive CLI. Their approvals are **scripted test responses**, never claims that a human reviewed an artifact.

The integration tests install Python socket/DNS tripwires in the client and MCP server subprocess. They verify that the child guard loaded and observed no network attempt. This is regression coverage, not an OS-level sandbox.

See [fresh verification details](docs/verification.md) for exact results and limits. The pinned mcp-agent version emits a Pydantic deprecation warning; the warning is left visible.

## Architecture

```text
Local JSON -> read-only FastMCP stdio server -> mcp-agent Agent.call_tool
           -> strict Source -> deterministic Draft + evidence hashes
           -> real HumanInputRequest -> exact approval -> local Markdown
```

- [`models.py`](src/release_notes_agent/models.py): strict data contracts
- [`core.py`](src/release_notes_agent/core.py): normalization, rendering, hashes
- [`server.py`](src/release_notes_agent/server.py): one snapshot, one read-only tool
- [`workflow.py`](src/release_notes_agent/workflow.py): mcp-agent orchestration and callback ownership
- [`review.py`](src/release_notes_agent/review.py): approval, terminal cleanup, and exclusive writes
- [`cli.py`](src/release_notes_agent/cli.py): user-facing commands

Direct runtime dependencies are pinned to mcp-agent 0.2.6, MCP SDK 1.30.0, and Pydantic 2.13.5. `uv.lock` pins the full dependency graph. No LLM is attached. Telemetry, tracing exports, unused OAuth helpers, and subagent auto-discovery are disabled.

## Scope and limitations

This is a single-user workflow guard, **not authentication**. The reviewer label is self-declared. Someone who can change the program or files can bypass it. The embedded receipt is an audit aid, never a reusable permission token. No signatures, access-control service, or durable distributed workflow are provided.

No live LLM evaluation, GitHub publisher, hosting, or production security certification is claimed. External publication would require a separate integration, trusted reviewer identity, destination-bound authorization, and a final server-side content check. See [SECURITY.md](SECURITY.md).

## Contributing and writing sample

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, offline checks, fixtures, packaging, and security reporting.

[Build a release-note workflow you can actually review](docs/article.md) explains the code and trade-offs as a technical article draft.

Built against the official [mcp-agent agent documentation](https://docs.mcp-agent.com/mcp-agent-sdk/core-components/agents), [mcp-agent source](https://github.com/lastmile-ai/mcp-agent), and [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk). This is an independent example, not an official LastMile AI tutorial. See [THIRD_PARTY.md](THIRD_PARTY.md) and [LICENSE](LICENSE).
