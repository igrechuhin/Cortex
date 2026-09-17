"""Native command input must not select an unrelated workspace."""

import io
import json
from pathlib import Path

import pytest

from cortex.setup import plugin_start
from tests.e2e.public_workflow_helpers import write_memory_bank


def _input(root: Path) -> dict[str, object]:
    return {
        "hook_event_name": "SessionStart",
        "cwd": str(root),
        "session_id": "command-smoke",
        "source": "startup",
    }


@pytest.mark.parametrize(
    "change",
    [
        {"hook_event_name": "PreCompact"},
        {"cwd": "relative"},
        {"cwd": "/"},
    ],
)
def test_startup_rejects_wrong_event_or_workspace(
    tmp_path: Path, change: dict[str, object]
) -> None:
    event = _input(tmp_path) | change

    with pytest.raises(ValueError):
        _ = plugin_start.startup_payload(json.dumps(event), "claude", tmp_path)

    assert not (tmp_path / ".cortex").exists()


@pytest.mark.parametrize("raw", ["[]", "not json", " " * 65537])
def test_startup_rejects_malformed_or_oversized_input(tmp_path: Path, raw: str) -> None:
    with pytest.raises(ValueError):
        _ = plugin_start.startup_payload(raw, "claude", tmp_path)

    assert not (tmp_path / ".cortex").exists()


def test_native_command_orients_real_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _ = write_memory_bank(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["plugin_start", "claude"])
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_input(tmp_path))))

    plugin_start.main()

    result = json.loads(capsys.readouterr().out)
    context = result["hookSpecificOutput"]["additionalContext"]
    assert "Python smoke" in context
    assert len(context) <= 3000


@pytest.mark.parametrize(
    "arguments,raw", [([], "{}"), (["claude"], "[]"), (["unsupported"], None)]
)
def test_native_command_failure_is_visible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
    raw: str | None,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["plugin_start", *arguments])
    payload = json.dumps(_input(tmp_path)) if raw is None else raw
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))

    with pytest.raises(SystemExit) as error:
        plugin_start.main()

    assert error.value.code == 1
    output = capsys.readouterr()
    assert output.err
    assert output.out == ""
