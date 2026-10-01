"""The only export path: display, await approval, re-check, exclusively create output."""

import asyncio
import json
import os
import re
import sys
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from .core import MAX_DRAFT_BYTES, load_draft
from .models import safe_text

RequestInput = Callable[[str], Awaitable[str]]


class ReviewBlocked(ValueError):
    """A review did not grant permission for this exact local export."""


def read_bounded(path: Path, limit: int) -> str:
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f"File exceeds {limit} byte limit")
    return raw.decode("utf-8")


def validate_path_display(path: Path) -> None:
    text = safe_text(str(path))
    if any(character in text for character in "\r\n\t"):
        raise ValueError("File paths must be single-line and contain no tabs")


async def terminal_response(prompt: str) -> str:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ReviewBlocked(
            "Approval requires an interactive terminal; no --yes bypass is provided"
        )
    print(prompt)
    print("Decision: ", end="", flush=True)
    loop = asyncio.get_running_loop()
    answer = loop.create_future()
    fd = sys.stdin.fileno()

    def read_line() -> None:
        if answer.done():
            return
        try:
            line = sys.stdin.readline()
            if not line:
                raise EOFError("Terminal closed before approval")
            answer.set_result(line.rstrip("\r\n"))
        except Exception as exc:
            answer.set_exception(exc)

    try:
        loop.add_reader(fd, read_line)
    except (NotImplementedError, OSError) as exc:
        raise ReviewBlocked("Interactive review requires a POSIX terminal (Linux/macOS)") from exc
    try:
        return await answer
    finally:
        loop.remove_reader(fd)


async def review_and_export(
    draft_path: Path,
    output_path: Path,
    reviewer: str,
    request_input: RequestInput,
) -> dict:
    """Gate an export on an exact answer from a trusted local callback.

    The injected callback is an application trust boundary, not remote authentication.
    Production CLI callers always use a TTY callback; tests inject labeled test responses.
    """
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 @._-]{0,99}", reviewer):
        raise ValueError("Reviewer must be a 1–100 character plain name or handle")
    validate_path_display(draft_path)
    validate_path_display(output_path)
    draft = load_draft(read_bounded(draft_path, MAX_DRAFT_BYTES))
    output_path = output_path.absolute()
    validate_path_display(output_path)
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError(f"Refusing to overwrite: {output_path}")
    if not output_path.parent.is_dir():
        raise FileNotFoundError(f"Output directory does not exist: {output_path.parent}")
    output_path = output_path.parent.resolve() / output_path.name
    validate_path_display(output_path)
    excluded = ", ".join(f"#{number}" for number in draft.excluded_prs) or "none"
    prompt = "\n".join(
        [
            "HUMAN REVIEW — LOCAL EXPORT ONLY",
            "",
            draft.markdown,
            "Review warnings:",
            *(f"- {warning}" for warning in draft.warnings),
            f"Excluded unmerged PRs: {excluded}",
            f"Reviewer label: {reviewer}",
            f"Destination: {output_path}",
            f"Draft SHA-256: {draft.digest}",
            "",
            "Read the draft and source evidence before approving. This exports a local file only.",
            f"Type APPROVE {draft.digest} to export this exact draft.",
            "Any other response declines. Nothing will be published to GitHub.",
        ]
    )
    try:
        response = await request_input(prompt)
    except Exception as exc:
        raise ReviewBlocked(f"Review failed closed: {type(exc).__name__}") from exc
    if response != f"APPROVE {draft.digest}":
        raise ReviewBlocked("Draft not approved; no export written")
    try:
        current = load_draft(read_bounded(draft_path, MAX_DRAFT_BYTES))
    except (OSError, ValueError) as exc:
        raise ReviewBlocked("Draft changed or became unreadable during review") from exc
    if current.digest != draft.digest:
        raise ReviewBlocked("Draft changed during review; review the new draft")
    receipt = {
        "decision": "approved",
        "digest": draft.digest,
        "source_sha256": draft.source_sha256,
        "reviewer_label": reviewer,
        "destination": str(output_path),
        "approved_at": datetime.now(UTC).isoformat(),
        "scope": "local-file-export-only",
        "identity_verified": False,
    }
    fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(draft.markdown)
        receipt_json = json.dumps(receipt, sort_keys=True)
        receipt_json = receipt_json.replace("<", "\\u003c").replace(">", "\\u003e")
        stream.write("\n<!-- Review receipt: " + receipt_json + " -->\n")
    return receipt
