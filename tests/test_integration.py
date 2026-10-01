import asyncio
import io
import json
import os
import socket
import sys
from pathlib import Path

import pytest

from release_notes_agent.core import build_draft, parse_source
from release_notes_agent.review import ReviewBlocked, terminal_response
from release_notes_agent.workflow import draft_from_mcp, review_with_mcp


@pytest.fixture
def no_outbound_network(monkeypatch):
    attempts = []
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def reject_connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            attempts.append(address)
            raise AssertionError(f"Unexpected outbound connection: {address}")
        return original_connect(sock, address)

    def reject_connect_ex(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            attempts.append(address)
            raise AssertionError(f"Unexpected outbound connection: {address}")
        return original_connect_ex(sock, address)

    def reject_dns(*args, **kwargs):
        attempts.append(args)
        raise AssertionError("Unexpected DNS request")

    monkeypatch.setattr(socket.socket, "connect", reject_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", reject_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", reject_dns)
    yield attempts
    assert attempts == []


async def test_actual_stdio_mcp_roundtrip(tmp_path, source_data, no_outbound_network, monkeypatch):
    from release_notes_agent import workflow

    original_settings = workflow.offline_settings
    log = tmp_path / "network-guard.log"

    def guarded_settings(path=None):
        settings = original_settings(path)
        if path is not None:
            settings.mcp.servers["changes"].env = {
                "PYTHONPATH": str(Path(__file__).parent / "network_guard"),
                "NETWORK_GUARD_LOG": str(log),
            }
        return settings

    monkeypatch.setattr(workflow, "offline_settings", guarded_settings)
    source = tmp_path / "source.json"
    source.write_text(json.dumps(source_data))
    result = await draft_from_mcp(source)
    assert result.draft == build_draft(parse_source(source_data))
    assert result.tools == ["changes_list_changes"]
    assert result.framework == "mcp-agent"
    assert result.model_calls == 0
    assert log.read_text() == "guard-loaded\n"


async def test_actual_mcp_agent_human_input_roundtrip(tmp_path, source_data, no_outbound_network):
    draft = build_draft(parse_source(source_data))
    path, output = tmp_path / "draft.json", tmp_path / "notes.md"
    path.write_text(draft.model_dump_json())
    requests = []

    async def test_callback(prompt):
        requests.append(prompt)
        return f"APPROVE {draft.digest}"

    receipt = await review_with_mcp(path, output, "automated-test", test_callback)
    assert len(requests) == 1
    assert receipt["decision"] == "approved"
    assert output.exists()


async def test_actual_mcp_agent_rejection(tmp_path, source_data, no_outbound_network):
    draft = build_draft(parse_source(source_data))
    path, output = tmp_path / "draft.json", tmp_path / "notes.md"
    path.write_text(draft.model_dump_json())

    async def reject(prompt):
        return "REJECT"

    with pytest.raises(ReviewBlocked):
        await review_with_mcp(path, output, "automated-test", reject)
    assert not output.exists()


def pending_human_callback_tasks():
    return {
        task
        for task in asyncio.all_tasks()
        if "Agent.request_human_input.<locals>.call_callback_and_signal"
        in task.get_coro().__qualname__
        and not task.done()
    }


@pytest.mark.parametrize("exit_mode", ["cancel", "timeout"])
async def test_actual_framework_closes_callback_on_review_exit(
    tmp_path,
    source_data,
    no_outbound_network,
    monkeypatch,
    exit_mode,
):
    from release_notes_agent import workflow

    draft = build_draft(parse_source(source_data))
    path, output = tmp_path / "draft.json", tmp_path / "notes.md"
    path.write_text(draft.model_dump_json())
    started, cleaned = asyncio.Event(), asyncio.Event()
    active_readers = 0

    async def waiting_reader(prompt):
        nonlocal active_readers
        active_readers += 1
        started.set()
        try:
            await asyncio.Future()
        finally:
            active_readers -= 1
            cleaned.set()

    if exit_mode == "timeout":
        original_request = workflow.HumanInputRequest

        def short_request(**kwargs):
            return original_request(**{**kwargs, "timeout_seconds": 1})

        monkeypatch.setattr(workflow, "HumanInputRequest", short_request)
    review = asyncio.create_task(review_with_mcp(path, output, "automated-test", waiting_reader))
    await asyncio.wait_for(started.wait(), timeout=5)
    try:
        if exit_mode == "cancel":
            review.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(review, timeout=5)
        else:
            with pytest.raises(ReviewBlocked):
                await asyncio.wait_for(review, timeout=5)
        assert cleaned.is_set(), "Callback cleanup did not run when the review exited"
        assert active_readers == 0
        assert not pending_human_callback_tasks()
        assert not output.exists()

        async def next_review(prompt):
            assert active_readers == 0, "A stale reader survived into the next review"
            return f"APPROVE {draft.digest}"

        receipt = await review_with_mcp(path, output, "subsequent-test", next_review)
        assert receipt["decision"] == "approved"
        assert not pending_human_callback_tasks()
    finally:
        pending = pending_human_callback_tasks()
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


async def test_framework_cancellation_removes_real_terminal_reader(
    tmp_path,
    source_data,
    no_outbound_network,
    monkeypatch,
):
    pty = pytest.importorskip("pty")
    draft = build_draft(parse_source(source_data))
    path, output = tmp_path / "draft.json", tmp_path / "notes.md"
    path.write_text(draft.model_dump_json())
    master, slave = pty.openpty()
    loop = asyncio.get_running_loop()
    registered = set()
    entered = asyncio.Event()
    original_add, original_remove = loop.add_reader, loop.remove_reader

    def track_add(fd, callback, *args):
        original_add(fd, callback, *args)
        if fd == slave:
            registered.add(fd)
            entered.set()

    def track_remove(fd):
        registered.discard(fd)
        return original_remove(fd)

    class TerminalOutput(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(loop, "add_reader", track_add)
    monkeypatch.setattr(loop, "remove_reader", track_remove)
    try:
        with os.fdopen(slave, "r") as terminal:
            monkeypatch.setattr(sys, "stdin", terminal)
            monkeypatch.setattr(sys, "stdout", TerminalOutput())
            review = asyncio.create_task(
                review_with_mcp(path, output, "scripted-terminal-test", terminal_response)
            )
            await asyncio.wait_for(entered.wait(), timeout=5)
            review.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(review, timeout=5)
            assert not registered
            assert not pending_human_callback_tasks()
            assert not output.exists()
            entered.clear()
            next_review = asyncio.create_task(
                review_with_mcp(path, output, "scripted-terminal-test", terminal_response)
            )
            await asyncio.wait_for(entered.wait(), timeout=5)
            assert registered == {slave}
            os.write(master, f"APPROVE {draft.digest}\n".encode())
            receipt = await asyncio.wait_for(next_review, timeout=5)
            assert receipt["decision"] == "approved"
            assert not registered
            assert not pending_human_callback_tasks()
    finally:
        os.close(master)
        pending = pending_human_callback_tasks()
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
