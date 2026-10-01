import json
import os
import subprocess
import sys


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "release_notes_agent", *map(str, args)],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "NO_COLOR": "1"},
    )


def test_cli_help():
    result = cli("--help")
    assert result.returncode == 0
    assert "draft" in result.stdout and "review" in result.stdout


def test_cli_draft_inspect_and_noninteractive_block(tmp_path, source_data):
    source, draft, output = (tmp_path / name for name in ["source.json", "draft.json", "notes.md"])
    source.write_text(json.dumps(source_data))
    result = cli("draft", "--input", source, "--output", draft)
    assert result.returncode == 0, result.stderr
    assert "Model calls: 0" in result.stdout
    assert draft.exists()
    result = cli("inspect", draft)
    assert result.returncode == 0
    assert "CSV export" in result.stdout and "SHA-256" in result.stdout
    result = cli("review", draft, "--output", output, "--reviewer", "tester")
    assert result.returncode == 2
    assert "interactive terminal" in result.stderr
    assert not output.exists()
    result = cli("draft", "--input", source, "--output", draft)
    assert result.returncode == 2
    assert "overwrite" in result.stderr


def test_cli_malformed_source_and_missing_draft(tmp_path):
    source = tmp_path / "bad.json"
    source.write_text("not json")
    result = cli("draft", "--input", source, "--output", tmp_path / "draft.json")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    result = cli("inspect", tmp_path / "missing.json")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
