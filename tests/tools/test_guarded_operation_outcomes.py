"""Finite domain refusals through real isolated guarded-operation consumers."""

import hashlib
import importlib.util
import json
import stat
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal, cast
from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import CallToolResult, TextContent

from cortex.core.exceptions import FileLockTimeoutError
from cortex.core.file_system import FileSystemManager
from cortex.memory.wal import wal_atomic_write_bytes
from cortex.tools.files import document_patch_operations as document
from cortex.tools.files.guarded_operation_outcome import GuardedOperationOutcome
from cortex.tools.plans.plan import plan
from cortex.tools.session.task_locking import claim_task

_Kind = Literal["document", "owner"]
_BODY = (
    b"---\r\ntitle: Guarded\r\nstatus: PENDING\r\nexecution: operator\r\n---\r\n"
    b"# Guarded\r\n\r\nOriginal prose.\r\n"
)
_TARGET = ".cortex/plans/guarded.md"


def _write(root: Path, relative: str = _TARGET, body: bytes = _BODY) -> Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    _ = target.write_bytes(body)
    target.chmod(0o640)
    return target


async def _invoke_owner(root: Path, target: str, payload: dict[str, object]) -> str:
    with (
        patch(
            "cortex.tools.plans.execution.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=str(root),
        ),
        patch("cortex.core.mcp_stability_usage.get_current_managers", return_value={}),
    ):
        return await plan(
            operation="set_execution", slug=target, content=json.dumps(payload)
        )


async def _invoke(
    root: Path,
    kind: _Kind,
    body: bytes = _BODY,
    /,
    target: str = _TARGET,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "expected_sha256": hashlib.sha256(body).hexdigest(),
        "dry_run": False,
    }
    if kind == "document":
        payload["replacements"] = [
            {"old": "Original prose.", "new": "Repaired prose.", "count": 1}
        ]
        payload.update(overrides)
        raw = await document.handle_document_patch(root, target, json.dumps(payload))
    else:
        payload.update(execution="agent", reason="Authorized correction")
        payload.update(overrides)
        raw = await _invoke_owner(root, target, payload)
    return cast(dict[str, object], json.loads(raw))


def _name(kind: _Kind) -> str:
    return _TARGET if kind == "document" else "guarded"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["document", "owner"])
@pytest.mark.parametrize("dry_run", [True, False])
async def test_stale_domain_refusal_is_repeatable_without_mutation(
    tmp_path: Path, kind: _Kind, dry_run: bool
) -> None:
    target = _write(tmp_path)
    for _ in range(2):
        result = await _invoke(
            tmp_path,
            kind,
            target=_name(kind),
            dry_run=dry_run,
            expected_sha256="0" * 64,
        )
        assert result["code"] == "STALE_BASE"
        assert result["mutation_performed"] is False
        assert result["target"] == _TARGET
        assert result["before_sha256"] == hashlib.sha256(_BODY).hexdigest()
        assert "after_sha256" not in result
        assert "Stale expected_sha256" in str(result["error"])
    assert target.read_bytes() == _BODY
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["document", "owner"])
@pytest.mark.parametrize("dry_run", [True, False])
async def test_policy_denial_keeps_validated_revision_and_bytes(
    tmp_path: Path, kind: _Kind, dry_run: bool
) -> None:
    target = _write(tmp_path)
    overrides: dict[str, object] = {"dry_run": dry_run}
    if kind == "document":
        overrides["replacements"] = [
            {"old": "# Guarded", "new": "# Changed", "count": 1}
        ]
    else:
        overrides["reason"] = "   "
    result = await _invoke(tmp_path, kind, target=_name(kind), **overrides)
    assert result["code"] == "POLICY_BLOCKED"
    assert result["mutation_performed"] is False
    if kind == "document":
        assert result["target"] == _TARGET
        assert result["before_sha256"] == hashlib.sha256(_BODY).hexdigest()
    else:
        assert result["target"] is None
        assert "before_sha256" not in result
    assert target.read_bytes() == _BODY
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["document", "owner"])
@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("guard", ["path", "symlink", "lock"])
async def test_path_policy_never_invents_unread_revision(
    tmp_path: Path, kind: _Kind, dry_run: bool, guard: str
) -> None:
    root = tmp_path / "workspace"
    target = _write(root)
    outside = _write(tmp_path, "outside.md")
    name = _name(kind)
    if guard == "path":
        name = "../outside.md"
    elif guard == "symlink":
        target.unlink()
        target.symlink_to(outside)
    else:
        target.with_suffix(".md.lock").symlink_to(outside)
    result = await _invoke(root, kind, target=name, dry_run=dry_run)
    assert result["code"] == "POLICY_BLOCKED"
    assert result["mutation_performed"] is False
    assert result["target"] == (_TARGET if guard == "lock" else None)
    assert ("before_sha256" in result) == (guard == "lock")
    assert target.read_bytes() == outside.read_bytes() == _BODY


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["document", "owner"])
@pytest.mark.parametrize("dry_run", [True, False])
async def test_schema_errors_are_not_domain_policy_refusals(
    tmp_path: Path, kind: _Kind, dry_run: bool
) -> None:
    target = _write(tmp_path)
    result = await _invoke(
        tmp_path, kind, target=_name(kind), dry_run=dry_run, extra=True
    )
    assert result["status"] == "error"
    assert result.get("code") is None
    assert result["error_type"] == "ValidationError"
    assert result["mutation_performed"] is False
    assert "before_sha256" not in result
    assert target.read_bytes() == _BODY


@pytest.mark.asyncio
@pytest.mark.parametrize("dry_run", [True, False])
async def test_real_foreign_roadmap_lock_blocks_preview_and_apply(
    tmp_path: Path, dry_run: bool
) -> None:
    relative = ".cortex/memory-bank/roadmap.md"
    body = b"# Roadmap\n\n- **Guarded task** - PENDING - Original prose.\n"
    target = _write(tmp_path, relative, body)
    with patch(
        "cortex.tools.session.task_locking.get_session_id", return_value="foreign"
    ):
        assert await claim_task(tmp_path, "Guarded task") is not None
    with patch("cortex.tools.files.lock_guard.get_session_id", return_value="consumer"):
        for _ in range(2):
            result = await _invoke(
                tmp_path, "document", body, relative, dry_run=dry_run
            )
            assert result["code"] == "POLICY_BLOCKED"
            assert "locked by another session" in str(result["error"])
            assert result["mutation_performed"] is False
            assert result["before_sha256"] == hashlib.sha256(body).hexdigest()
    assert target.read_bytes() == body
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["document", "owner"])
@pytest.mark.parametrize("change", ["bytes", "symlink"])
async def test_final_preimage_check_preserves_policy_over_stale(
    tmp_path: Path, kind: _Kind, change: str
) -> None:
    root = tmp_path / "workspace"
    target = _write(root)
    outside = _write(tmp_path, "outside.md")
    changed = _BODY + b"Concurrent edit\r\n"

    def race(staging: Path, staged: Path, after: bytes) -> None:
        wal_atomic_write_bytes(staging, staged, after)
        if change == "bytes":
            _ = target.write_bytes(changed)
        else:
            target.unlink()
            target.symlink_to(outside)

    with patch.object(document, "wal_atomic_write_bytes", race):
        result = await _invoke(root, kind, target=_name(kind))
    assert result["code"] == ("STALE_BASE" if change == "bytes" else "POLICY_BLOCKED")
    assert result["mutation_performed"] is False
    observed = changed if change == "bytes" else _BODY
    assert result["before_sha256"] == hashlib.sha256(observed).hexdigest()
    assert target.read_bytes() == (changed if change == "bytes" else _BODY)
    assert outside.read_bytes() == _BODY


def _assert_actual_mutation(target: Path, result: dict[str, object]) -> None:
    assert result["status"] == "error"
    assert result["mutation_performed"] is True
    assert result.get("code") is None
    assert result["after_sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert target.read_bytes() != _BODY
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["document", "owner"])
@pytest.mark.parametrize("failure", ["cleanup", "release"])
async def test_post_replacement_failure_reports_actual_mutation(
    tmp_path: Path,
    kind: _Kind,
    failure: str,
    consume: Callable[[CallToolResult, Path], None],
) -> None:
    target = _write(tmp_path)
    cleanup = TemporaryDirectory[str].cleanup
    release = FileSystemManager.release_lock

    def cleanup_then_fail(directory: TemporaryDirectory[str]) -> None:
        cleanup(directory)
        raise OSError("Staging cleanup failed")

    async def release_then_fail(manager: FileSystemManager, lock: Path) -> None:
        await release(manager, lock)
        raise OSError("Lock release failed")

    seam = (
        patch.object(TemporaryDirectory, "cleanup", cleanup_then_fail)
        if failure == "cleanup"
        else patch.object(FileSystemManager, "release_lock", release_then_fail)
    )
    with seam:
        result = await _invoke(tmp_path, kind, target=_name(kind))
    _assert_actual_mutation(target, result)
    if kind == "owner":
        with pytest.raises(RuntimeError, match="read back before any retry"):
            consume(_response(result), tmp_path)
        assert result["after_sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["document", "owner"])
@pytest.mark.parametrize("failure", ["io", "timeout"])
async def test_non_domain_failures_remain_unclassified(
    tmp_path: Path, kind: _Kind, failure: str
) -> None:
    target = _write(tmp_path)
    error = (
        OSError("Unreadable lock")
        if failure == "io"
        else FileLockTimeoutError("guarded.md", 1)
    )
    with patch.object(FileSystemManager, "acquire_lock", side_effect=error):
        result = await _invoke(tmp_path, kind, target=_name(kind))
    assert result["status"] == "error"
    assert result.get("code") is None
    assert result["mutation_performed"] is False
    assert target.read_bytes() == _BODY


def test_finite_vocabulary_excludes_unimplemented_decision_boundary() -> None:
    assert {code.value for code in GuardedOperationOutcome} == {
        "STALE_BASE",
        "POLICY_BLOCKED",
    }


@pytest.fixture
def consume() -> Callable[[CallToolResult, Path], None]:
    script = Path(__file__).resolve().parents[2] / "scripts/set_plan_execution.py"
    spec = importlib.util.spec_from_file_location("guarded_execution_cli", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(
        Callable[[CallToolResult, Path], None], getattr(module, "_validate_response")
    )


def _response(result: dict[str, object], is_error: bool = False) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(result))], isError=is_error
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("dry_run", [True, False])
async def test_cli_consumes_real_backend_preview_apply_and_noop(
    tmp_path: Path, dry_run: bool, consume: Callable[[CallToolResult, Path], None]
) -> None:
    target = _write(tmp_path)
    result = await _invoke(tmp_path, "owner", target="guarded", dry_run=dry_run)
    consume(_response(result), tmp_path)
    body = target.read_bytes()
    result = await _invoke(
        tmp_path,
        "owner",
        body,
        "guarded",
        execution="operator" if dry_run else "agent",
    )
    consume(_response(result), tmp_path)
    assert result["mutation_performed"] is False
    assert target.read_bytes() == body


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["STALE_BASE", "POLICY_BLOCKED"])
async def test_cli_reports_real_denial_without_mutating_or_retrying(
    tmp_path: Path,
    code: str,
    consume: Callable[[CallToolResult, Path], None],
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = _write(tmp_path)
    overrides = (
        {"expected_sha256": "0" * 64} if code == "STALE_BASE" else {"reason": " "}
    )
    result = await _invoke(tmp_path, "owner", target="guarded", **overrides)
    with pytest.raises(RuntimeError, match=code):
        consume(_response(result), tmp_path)
    assert str(result["error"]) in capsys.readouterr().out
    assert target.read_bytes() == _BODY


@pytest.mark.parametrize("code", ["STALE_BASE", "POLICY_BLOCKED"])
def test_cli_root_guard_precedes_typed_denial(
    tmp_path: Path, code: str, consume: Callable[[CallToolResult, Path], None]
) -> None:
    result: dict[str, object] = {
        "status": "error",
        "operation": "set_execution",
        "project_root": str(tmp_path / "wrong"),
        "target": None,
        "code": code,
        "error": "Denied",
        "mutation_performed": False,
    }
    with pytest.raises(RuntimeError, match="sole advertised root"):
        consume(_response(result), tmp_path)


@pytest.mark.parametrize(
    "change",
    [
        {"code": "DECISION_REQUIRED"},
        {"code": "UNKNOWN"},
        {"mutation_performed": "false"},
        {"mutation_performed": True},
        {"status": "unknown"},
        {"code": None},
        {"error": None},
        {"code": "STALE_BASE"},
        {"target": _TARGET},
        {"before_sha256": "0" * 64},
        {"after_sha256": "1" * 64},
    ],
)
def test_cli_rejects_unknown_malformed_or_uncertain_refusal(
    tmp_path: Path,
    change: dict[str, object],
    consume: Callable[[CallToolResult, Path], None],
) -> None:
    result: dict[str, object] = {
        "status": "error",
        "operation": "set_execution",
        "project_root": str(tmp_path),
        "target": None,
        "code": "POLICY_BLOCKED",
        "error": "Diagnostic",
        "mutation_performed": False,
        **change,
    }
    with pytest.raises(RuntimeError, match="read back before any retry"):
        consume(_response(result), tmp_path)


@pytest.mark.parametrize("raw", ["not json", "[]", "{}"])
def test_cli_rejects_missing_or_nonobject_response(
    tmp_path: Path, raw: str, consume: Callable[[CallToolResult, Path], None]
) -> None:
    response = CallToolResult(content=[TextContent(type="text", text=raw)])
    with pytest.raises(RuntimeError, match="read back before any retry"):
        consume(response, tmp_path)


@pytest.mark.parametrize(
    "change",
    [
        {"target": None},
        {"target": "outside.md"},
        {"before_sha256": None},
        {"before_sha256": "invalid"},
        {"after_sha256": None},
        {"dry_run": None},
        {"dry_run": True},
        {"code": "POLICY_BLOCKED"},
        {"error": "Unexpected diagnostic"},
        {"mutation_performed": False},
        {"after_sha256": "0" * 64},
    ],
)
def test_cli_rejects_contradictory_or_incomplete_success(
    tmp_path: Path,
    change: dict[str, object],
    consume: Callable[[CallToolResult, Path], None],
) -> None:
    result: dict[str, object] = {
        "status": "success",
        "operation": "set_execution",
        "project_root": str(tmp_path),
        "target": _TARGET,
        "before_sha256": "0" * 64,
        "after_sha256": "1" * 64,
        "dry_run": False,
        "mutation_performed": True,
        **change,
    }
    with pytest.raises(RuntimeError, match="read back before any retry"):
        consume(_response(result), tmp_path)


@pytest.mark.parametrize("status", ["success", "error"])
def test_cli_transport_error_requires_readback(
    tmp_path: Path, status: str, consume: Callable[[CallToolResult, Path], None]
) -> None:
    result: dict[str, object] = {
        "status": status,
        "operation": "set_execution",
        "project_root": str(tmp_path),
        "target": _TARGET,
        "before_sha256": "0" * 64,
        "after_sha256": "1" * 64,
        "dry_run": True,
        "mutation_performed": False,
        **({"code": "POLICY_BLOCKED", "error": "Denied"} if status == "error" else {}),
    }
    with pytest.raises(RuntimeError, match="read back before any retry"):
        consume(_response(result, is_error=True), tmp_path)


@pytest.mark.asyncio
async def test_preview_release_error_keeps_only_observed_revision(
    tmp_path: Path, consume: Callable[[CallToolResult, Path], None]
) -> None:
    target = _write(tmp_path)
    release = FileSystemManager.release_lock

    async def release_then_fail(manager: FileSystemManager, lock: Path) -> None:
        await release(manager, lock)
        raise OSError("Preview lock release failed")

    with patch.object(FileSystemManager, "release_lock", release_then_fail):
        result = await _invoke(tmp_path, "owner", target="guarded", dry_run=True)
    assert result["status"] == "error"
    assert result["mutation_performed"] is False
    assert result["before_sha256"] == hashlib.sha256(_BODY).hexdigest()
    assert "after_sha256" not in result
    assert result.get("code") is None
    with pytest.raises(RuntimeError, match="read back before any retry"):
        consume(_response(result), tmp_path)
    assert target.read_bytes() == _BODY
