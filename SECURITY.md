# Security and trust boundaries

This project illustrates a human-review workflow. It is not a multi-user authorization system or a secure sandbox.

## Trusted components

The local Python code, installed dependencies, application configuration, terminal callback, and operating-system user account are trusted. The reviewer label is self-declared, not verified. A caller injecting a custom Python callback is trusted application code; tests use this seam to supply scripted decisions.

## Untrusted data

Every PR title, body, label, and link is untrusted. Input is bounded and strictly validated. URLs must match the declared GitHub repository and PR number. Titles are HTML-escaped and Markdown-escaped. Terminal control and invisible formatting characters are rejected. Bodies are retained in JSON and never rendered as approval instructions or executed. The instruction-like phrase heuristic is advisory, incomplete, and not a security classifier.

## Enforced workflow properties

- The local MCP server loads one explicit, validated snapshot. It exposes no caller-controlled file path and only one read-only tool
- No LLM or remote API is used. Telemetry, tracing exports, OAuth helpers, and automatic subagent discovery are disabled
- The agent cannot call an export or publish tool
- Approval requires the exact draft digest through the CLI's interactive terminal callback. Redirected input and a blanket `--yes` shortcut are not supported
- The displayed destination is validated after absolute-path and symlink-parent resolution and fixed before review. A changed or unreadable draft fails closed after review
- Exclusive file creation refuses existing files and final-component symlinks, including a competing writer creating the destination during review
- Errors, rejection, cancellation, EOF, and invalid responses never grant permission
- The application owns the framework callback task lifecycle and cancels/awaits outstanding input callbacks before review cleanup

## What the hashes prove

The source hash covers canonical normalized JSON. The draft hash covers the source, source hash, rendered text, warnings, exclusions, schema, and generator. Re-loading also regenerates the expected draft to detect inconsistent derived fields. These are integrity checks, not signatures. They cannot prove source authenticity, reviewer identity, completeness of a release range, or semantic accuracy of a PR title.

## Outside scope

A malicious same-user process can modify code, impersonate terminal input, replace files, or write directly to the output directory. Symlink/parent-directory races by an adversary with filesystem access are not a supported security boundary. A full disk or I/O failure can leave a partial exclusively-created output; inspect the error and use a fresh filename. Export is not a transaction spanning a remote service.

The Python socket tripwire in tests detects conventional Python network calls. It is not an OS firewall and does not defend against malicious dependencies or native-code networking. Install reviewed dependencies in an environment appropriate for the source data's sensitivity.

Do not share draft JSON or put confidential PR bodies in a public repository without reviewing the embedded source snapshot. There is no redaction or secret-detection guarantee.

## Reporting

Use the repository's issue tracker for non-sensitive, reproducible defects after publication. For sensitive vulnerability details, use private vulnerability reporting if available or ask the maintainer for a private channel. Do not include secrets or private source material in public reports.
