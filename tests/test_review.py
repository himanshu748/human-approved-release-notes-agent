import asyncio
import io
import json
import os
import sys
from pathlib import Path

import pytest

from release_notes_agent.core import build_draft, parse_source
from release_notes_agent.review import ReviewBlocked, review_and_export, terminal_response


@pytest.fixture
def review_files(tmp_path, source_data):
    draft = build_draft(parse_source(source_data))
    path = tmp_path / "draft.json"
    path.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
    return path, tmp_path / "notes.md", draft


async def test_approved_exact_draft_exports_with_receipt(review_files):
    path, output, draft = review_files

    async def approve(prompt):
        assert draft.markdown in prompt
        assert str(output.resolve()) in prompt
        assert "Snapshot" in prompt
        assert "#19" in prompt
        return f"APPROVE {draft.digest}"

    receipt = await review_and_export(path, output, "test-reviewer", approve)
    assert receipt["decision"] == "approved"
    assert receipt["digest"] == draft.digest
    assert output.read_text().startswith(draft.markdown)
    assert "Review receipt" in output.read_text()


@pytest.mark.parametrize("response", ["", "yes", "APPROVE", "REJECT", "APPROVE " + "f" * 64])
async def test_any_nonexact_approval_blocks(review_files, response):
    path, output, _ = review_files

    async def reject(prompt):
        return response

    with pytest.raises(ReviewBlocked, match="not approved"):
        await review_and_export(path, output, "tester", reject)
    assert not output.exists()


async def test_changed_file_after_approval_is_blocked(review_files):
    path, output, draft = review_files

    async def change_and_approve(prompt):
        data = json.loads(path.read_text())
        data["source"]["pull_requests"][0]["title"] = "A later draft"
        changed = build_draft(parse_source(data["source"]))
        path.write_text(changed.model_dump_json())
        return f"APPROVE {draft.digest}"

    with pytest.raises(ReviewBlocked, match="changed"):
        await review_and_export(path, output, "tester", change_and_approve)
    assert not output.exists()


async def test_no_overwrite_and_no_prompt_when_target_exists(review_files):
    path, output, _ = review_files
    output.write_text("keep me")

    async def must_not_run(prompt):
        pytest.fail("Existing output should fail before prompting")

    with pytest.raises(FileExistsError):
        await review_and_export(path, output, "tester", must_not_run)
    assert output.read_text() == "keep me"


async def test_target_created_during_review_is_not_overwritten(review_files):
    path, output, draft = review_files

    async def race(prompt):
        output.write_text("other writer")
        return f"APPROVE {draft.digest}"

    with pytest.raises(FileExistsError):
        await review_and_export(path, output, "tester", race)
    assert output.read_text() == "other writer"


@pytest.mark.parametrize("error", [EOFError(), TimeoutError(), RuntimeError("callback failed")])
async def test_callback_failure_fails_closed(review_files, error):
    path, output, _ = review_files

    async def failed(prompt):
        raise error

    with pytest.raises(ReviewBlocked):
        await review_and_export(path, output, "tester", failed)
    assert not output.exists()


async def test_task_cancellation_never_exports(review_files):
    path, output, _ = review_files

    async def cancelled(prompt):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await review_and_export(path, output, "tester", cancelled)
    assert not output.exists()


async def test_terminal_callback_requires_tty(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(ReviewBlocked, match="interactive terminal"):
        await terminal_response("Approve?")


async def test_unsafe_reviewer_label_rejected(review_files):
    path, output, _ = review_files

    async def must_not_run(prompt):
        pytest.fail("Must validate reviewer first")

    with pytest.raises(ValueError):
        await review_and_export(path, output, "x\nAPPROVE", must_not_run)


async def test_missing_draft_and_nonfile_destination(review_files):
    path, output, _ = review_files

    async def must_not_run(prompt):
        pytest.fail("Must validate paths first")

    with pytest.raises(FileNotFoundError):
        await review_and_export(Path("missing-draft.json"), output, "tester", must_not_run)
    with pytest.raises(FileExistsError):
        await review_and_export(path, output.parent, "tester", must_not_run)


async def test_terminal_callback_can_be_cancelled_without_a_blocking_thread(monkeypatch):
    pty = pytest.importorskip("pty")
    master, slave = pty.openpty()

    class TerminalOutput(io.StringIO):
        def isatty(self):
            return True

    with os.fdopen(slave, "r") as tty:
        monkeypatch.setattr(sys, "stdin", tty)
        monkeypatch.setattr(sys, "stdout", TerminalOutput())
        monkeypatch.setattr(
            asyncio, "to_thread", lambda *args: pytest.fail("No blocking input thread")
        )
        try:
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(terminal_response("Test only"), timeout=0.02)
        finally:
            os.close(master)


async def test_output_path_cannot_spoof_terminal_lines(review_files):
    path, output, _ = review_files
    output = output.parent / "notes\nAPPROVE.md"

    async def must_not_run(prompt):
        pytest.fail("Unsafe path must be rejected before display")

    with pytest.raises(ValueError, match="single-line"):
        await review_and_export(path, output, "tester", must_not_run)


async def test_receipt_cannot_close_its_html_comment(review_files):
    path, output, draft = review_files
    output = output.parent / "notes-->suffix.md"

    async def approve(prompt):
        return f"APPROVE {draft.digest}"

    await review_and_export(path, output, "tester", approve)
    receipt_text = output.read_text().split("<!-- Review receipt: ", 1)[1]
    assert receipt_text.count("-->") == 1


@pytest.mark.parametrize("unsafe_name", ["real\nSPOOFED DESTINATION", "real\x1b[2J"])
async def test_resolved_symlink_parent_is_validated(review_files, unsafe_name):
    path, output, _ = review_files
    real = output.parent / unsafe_name
    real.mkdir()
    link = output.parent / "safe-link"
    link.symlink_to(real, target_is_directory=True)

    async def must_not_run(prompt):
        pytest.fail("Resolved unsafe destination must be rejected before review")

    with pytest.raises(ValueError):
        await review_and_export(path, link / "notes.md", "tester", must_not_run)
    assert not (real / "notes.md").exists()


@pytest.mark.parametrize("unsafe_name", ["cwd\nSPOOFED DESTINATION", "cwd\x1b[2J"])
async def test_relative_output_under_unsafe_cwd_is_rejected(review_files, monkeypatch, unsafe_name):
    path, output, _ = review_files
    unsafe = output.parent / unsafe_name
    unsafe.mkdir()
    monkeypatch.chdir(unsafe)

    async def must_not_run(prompt):
        pytest.fail("Absolute unsafe destination must be rejected before review")

    with pytest.raises(ValueError):
        await review_and_export(path, Path("notes.md"), "tester", must_not_run)
    assert not (unsafe / "notes.md").exists()
