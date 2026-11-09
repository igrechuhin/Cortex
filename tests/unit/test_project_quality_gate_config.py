"""Project timeout budgets survive sessions without affecting other projects."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.quality_gate_config import (
    configure_quality_gate,
    effective_test_timeout,
    quality_gate_config_path,
)

# AI: Exercise the same private resolution and routing entrypoints used by MCP.
from cortex.tools.execution.pre_commit_zero_arg_tools import (
    _read_quality_gate_config,  # pyright: ignore[reportPrivateUsage]
)
from cortex.tools.session.pipeline_handoff import (
    _dispatch,  # pyright: ignore[reportPrivateUsage]
    _dispatch_sync,  # pyright: ignore[reportPrivateUsage]
)


def test_unconfigured_project_uses_fifteen_minute_default(tmp_path: Path) -> None:
    assert effective_test_timeout(tmp_path) == 900
    assert not quality_gate_config_path(tmp_path).exists()


def test_read_only_configuration_does_not_create_files(tmp_path: Path) -> None:
    result = json.loads(configure_quality_gate(tmp_path, None))
    assert result["config"] == {"test_timeout": None}
    assert result["effective_default_test_timeout"] == 900
    assert result["mutation_performed"] is False
    assert not (tmp_path / ".cortex").exists()


def test_project_timeout_survives_fresh_session_and_reload(tmp_path: Path) -> None:
    result = json.loads(configure_quality_gate(tmp_path, '{"test_timeout":10800}'))
    assert result["status"] == "ok"
    assert result["scope"] == "project"
    assert result["effective_default_test_timeout"] == 10800
    with patch(
        "cortex.tools.session.pipeline_handoff_session.get_session_id", return_value=""
    ):
        assert _read_quality_gate_config(tmp_path)[:3] == (10800, 0.9, True)
    assert json.loads(configure_quality_gate(tmp_path, None))["config"] == {
        "test_timeout": 10800
    }


@pytest.mark.parametrize(
    "requested,expected", [(600, 600), (2700, 2700), (14400, 14400)]
)
def test_explicit_session_timeout_overrides_project_budget(
    tmp_path: Path, requested: int, expected: int
) -> None:
    _ = configure_quality_gate(tmp_path, '{"test_timeout":10800}')
    phase = tmp_path / ".cortex" / ".session" / "fresh-run" / "commit"
    phase.mkdir(parents=True)
    _ = (phase / "checks-task.json").write_text(json.dumps({"test_timeout": requested}))
    with patch(
        "cortex.tools.session.pipeline_handoff_session.get_session_id",
        return_value="fresh-run",
    ):
        assert _read_quality_gate_config(tmp_path)[0] == expected


def test_project_configuration_does_not_leak_to_other_root(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _ = configure_quality_gate(first, '{"test_timeout":10800}')
    assert effective_test_timeout(first) == 10800
    assert effective_test_timeout(second) == 900
    assert not quality_gate_config_path(second).exists()


@pytest.mark.parametrize(
    "payload",
    [
        '{"test_timeout":0}',
        '{"test_timeout":-1}',
        '{"test_timeout":true}',
        '{"test_timeout":1.5}',
        '{"test_timeout":"10800"}',
        '{"test_timeout":10800,"unexpected":1}',
        "{}",
        "[]",
        "null",
        "{",
    ],
)
def test_invalid_input_preserves_existing_config(tmp_path: Path, payload: str) -> None:
    _ = configure_quality_gate(tmp_path, '{"test_timeout":10800}')
    path = quality_gate_config_path(tmp_path)
    before = path.read_bytes()
    result = json.loads(configure_quality_gate(tmp_path, payload))
    assert result["status"] == "error"
    assert path.read_bytes() == before


def test_explicit_null_restores_global_default(tmp_path: Path) -> None:
    _ = configure_quality_gate(tmp_path, '{"test_timeout":10800}')
    result = json.loads(configure_quality_gate(tmp_path, '{"test_timeout":null}'))
    assert result["status"] == "ok"
    assert effective_test_timeout(tmp_path) == 900


def test_project_can_choose_less_than_global_default(tmp_path: Path) -> None:
    _ = configure_quality_gate(tmp_path, '{"test_timeout":300}')
    assert effective_test_timeout(tmp_path) == 300
    with patch(
        "cortex.tools.session.pipeline_handoff_session.get_session_id", return_value=""
    ):
        assert _read_quality_gate_config(tmp_path)[0] == 300


def test_force_fresh_session_inherits_project_timeout(tmp_path: Path) -> None:
    _ = configure_quality_gate(tmp_path, '{"test_timeout":7200}')
    phase = tmp_path / ".cortex" / ".session" / "fresh-run" / "commit"
    phase.mkdir(parents=True)
    _ = (phase / "checks-task.json").write_text('{"force_fresh":true}')
    with patch(
        "cortex.tools.session.pipeline_handoff_session.get_session_id",
        return_value="fresh-run",
    ):
        assert _read_quality_gate_config(tmp_path)[:3] == (7200, 0.9, True)


def test_corrupt_persisted_config_fails_before_gate_can_start(tmp_path: Path) -> None:
    _ = configure_quality_gate(tmp_path, '{"test_timeout":10800}')
    _ = quality_gate_config_path(tmp_path).write_text('{"test_timeout":"wrong"}')
    with pytest.raises(ValueError):
        _ = _read_quality_gate_config(tmp_path)


def test_configuration_dispatch_does_not_publish_pipeline_result(
    tmp_path: Path,
) -> None:
    result = _dispatch_sync(
        tmp_path, "configure_quality_gate", "default", None, '{"test_timeout":10800}'
    )
    assert json.loads(result)["config"] == {"test_timeout": 10800}
    assert not (tmp_path / ".cortex" / ".session").exists()
    readback = _dispatch_sync(tmp_path, "configure_quality_gate", "default", None, None)
    assert json.loads(readback)["mutation_performed"] is False


def test_external_config_symlink_is_rejected(tmp_path: Path) -> None:
    project, external = tmp_path / "project", tmp_path / "outside.json"
    _ = external.write_text('{"test_timeout":600}')
    path = quality_gate_config_path(project)
    path.parent.mkdir(parents=True)
    path.symlink_to(external)
    result = json.loads(configure_quality_gate(project, '{"test_timeout":10800}'))
    assert result["status"] == "error"
    assert external.read_text() == '{"test_timeout":600}'


def test_external_config_directory_is_rejected(tmp_path: Path) -> None:
    project, external = tmp_path / "project", tmp_path / "external"
    external.mkdir()
    (project / ".cortex").mkdir(parents=True)
    (project / ".cortex" / "config").symlink_to(external, target_is_directory=True)
    result = json.loads(configure_quality_gate(project, '{"test_timeout":10800}'))
    assert result["status"] == "error"
    assert list(external.iterdir()) == []


def test_atomic_write_failure_keeps_old_config_and_cleans_temporary(
    tmp_path: Path,
) -> None:
    _ = configure_quality_gate(tmp_path, '{"test_timeout":10800}')
    with patch.object(Path, "replace", side_effect=OSError("write refused")):
        result = json.loads(configure_quality_gate(tmp_path, '{"test_timeout":14400}'))
    assert result["status"] == "error"
    assert effective_test_timeout(tmp_path) == 10800
    assert list(quality_gate_config_path(tmp_path).parent.glob(".quality-gate-*")) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("embedded", [False, True])
async def test_public_routing_accepts_object_payload(
    tmp_path: Path, embedded: bool
) -> None:
    data: dict[str, object] = {"test_timeout": 10800}
    operation = "configure_quality_gate"
    if embedded:
        data["operation"] = operation
        operation = "read_state"
    with patch(
        "cortex.tools.session.pipeline_handoff.get_or_resolve_project_root",
        new=AsyncMock(return_value=str(tmp_path)),
    ):
        result = await _dispatch(operation, "default", None, data, None)
    assert json.loads(result)["config"] == {"test_timeout": 10800}


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["configure_quality_gate", "read_state"])
async def test_stripped_arguments_do_not_reset_policy(
    tmp_path: Path, operation: str
) -> None:
    _ = configure_quality_gate(tmp_path, '{"test_timeout":10800}')
    with patch(
        "cortex.tools.session.pipeline_handoff.get_or_resolve_project_root",
        new=AsyncMock(return_value=str(tmp_path)),
    ):
        _ = await _dispatch(operation, "default", None, None, None)
    assert effective_test_timeout(tmp_path) == 10800
