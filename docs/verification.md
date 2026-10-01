# Verification record

Freshly verified on 2026-10-01 UTC. This is a newly rebuilt source bundle; the results below apply to its current source and regenerated lockfile, not to any earlier archive.

## Environment and checks

- Linux, Python 3.12.14
- mcp-agent 0.2.6, MCP Python SDK 1.30.0, Pydantic 2.13.5
- pytest 9.1.1 and Ruff 0.16.9
- Runtime dependencies installed from PyPI; full resolution in `uv.lock`
- `.venv/bin/python -m pytest -q`: **61 passed, one upstream warning, 17.15 seconds**
- `.venv/bin/ruff check src tests`: passed
- `.venv/bin/ruff format --check src tests`: passed, 15 files already formatted
- `python -m compileall -q src`: passed
- `uv lock --check --offline`: passed
- `uv build --offline`: wheel and source distribution built
- Fresh non-editable wheel installation: draft and preview were byte-identical to the committed fixture; the imported module came from the clean environment's site-packages

All application tests use local fixtures or temporary files. No provider credentials, GitHub authentication, live LLM, or hosted service was used. Initial dependency installation requires internet access to download open-source packages.

## What the tests exercised

- Real MCPApp startup/shutdown, FastMCP stdio server, tool discovery, and Agent.call_tool
- Exactly one discovered source tool: `changes_list_changes`
- Actual Agent.request_human_input approve/reject cycles
- Scripted pseudo-terminal approval and rejection through the CLI
- Non-TTY refusal without export
- Strict types, bounded input, canonical PR URLs, duplicate rejection, normalized ordering
- Escaped markup, control-character rejection, and safe receipt formatting
- Tampered drafts even when an attacker recomputes the outer digest
- Draft changes during review and exclusive output creation under competing writes
- Callback failure, cancellation, one-second framework timeout, and callback-task cleanup
- Actual terminal-reader cleanup followed by another review on the same event loop
- Final destination validation after absolute-path and symlink-parent resolution

The integration tests block conventional Python TCP/IP connection and DNS operations. The MCP server subprocess loads its own tripwire and records `guard-loaded`; no blocked network attempts occurred. These guards are test instrumentation, not a production security sandbox.

## Fixture fingerprint

The freshly regenerated `examples/draft.json` has this canonical draft digest:

```text
4938ac49169cd29471523b91ce78689aaf4ff9edc027aa498dd11c3cc8ada93e
```

This value is stored inside the JSON; it is not the SHA-256 of the pretty-printed file bytes. The repository and PRs are fictional. No successful test export is presented as human-approved.

## Limits and retained reliability observation

No external publisher, hosted UI, live model, or remote CI was tested. Python 3.11 and macOS are declared-compatible targets but were not run in this environment. Interactive review is POSIX-only. The upstream Pydantic classmethod-validator deprecation warning remains visible.

During earlier development, one CLI subprocess exceeded a 30-second timeout after printing its correct draft result. Subsequent repetitions did not establish a root cause. The new complete suite passed, but this historical intermittent observation is still unresolved; no fix or production-hardening claim is made for it.

The tests supply scripted approval responses. The reviewer label is self-declared and no authentication guarantee is offered. Code review and passing tests do not constitute an independent security audit.
