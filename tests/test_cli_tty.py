"""Scripted pseudo-terminal tests. These are not real human approvals."""

import os
import select
import subprocess
import sys
import time

import pytest

from release_notes_agent.core import build_draft, parse_source

pty = pytest.importorskip("pty")


@pytest.mark.parametrize("approve", [True, False])
def test_scripted_tty_approval_and_rejection(tmp_path, source_data, approve):
    draft = build_draft(parse_source(source_data))
    path, output = tmp_path / "draft.json", tmp_path / "notes.md"
    path.write_text(draft.model_dump_json())
    master, slave = pty.openpty()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "release_notes_agent",
            "review",
            str(path),
            "--output",
            str(output),
            "--reviewer",
            "scripted-tty-test",
        ],
        stdin=slave,
        stdout=slave,
        stderr=slave,
    )
    os.close(slave)
    transcript = b""
    try:
        deadline = time.monotonic() + 20
        while b"Decision: " not in transcript:
            assert time.monotonic() < deadline, transcript.decode(errors="replace")
            ready, _, _ = select.select([master], [], [], 0.1)
            if ready:
                transcript += os.read(master, 65536)
            assert process.poll() is None, transcript.decode(errors="replace")
        answer = f"APPROVE {draft.digest}" if approve else "REJECT"
        os.write(master, (answer + "\n").encode())
        assert process.wait(timeout=15) == (0 if approve else 2)
        assert output.exists() is approve
        if approve:
            assert "scripted-tty-test" in output.read_text()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
