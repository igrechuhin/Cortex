from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.tools.optimization import handlers


def count_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def _write_shared_files(tmp_path: Path) -> None:
    _ = (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo-app"\nrequires-python = ">=3.13"\n',
        encoding="utf-8",
    )
    memory_bank = tmp_path / ".cortex" / "memory-bank"
    _ = memory_bank.mkdir(parents=True)
    _ = (memory_bank / "activeContext.md").write_text(
        "## Current Focus\n\nactive task\n\n## Blockers\n\nblocker one",
        encoding="utf-8",
    )
    _ = (memory_bank / "progress.md").write_text(
        "## Decision\n\ndecision text", encoding="utf-8"
    )
    session_dir = tmp_path / ".cortex" / ".session"
    _ = session_dir.mkdir(parents=True)
    _ = (session_dir / "session-goal.md").write_text("Goal A\nGoal B", encoding="utf-8")


def _patch_context_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def _fake_load_context_impl(**_: object) -> str:
        return '{"status":"success","context":"base"}'

    async def _fake_build_payload(base_payload: str, _: Path) -> str:
        return base_payload

    async def _fake_project_root(_: object, __: object) -> Path:
        return tmp_path

    monkeypatch.setattr(handlers, "load_context_impl", _fake_load_context_impl)
    monkeypatch.setattr(
        handlers, "build_context_resource_payload_async", _fake_build_payload
    )
    monkeypatch.setattr(handlers, "resolve_project_root_async", _fake_project_root)


@pytest.mark.asyncio
async def test_context_resource_default_includes_l0_l1_and_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_shared_files(tmp_path)
    monkeypatch.setattr(
        "cortex.core.session_config.read_session_config",
        lambda: {
            "task_description": "general session context",
            "context_layers": ["l0", "l1"],
        },
    )
    _patch_context_runtime(monkeypatch, tmp_path)
    handlers.invalidate_context_resource_cache()

    payload = json.loads(await handlers.load_context())
    layered_context = str(payload["layered_context"])

    assert payload["context_layers_loaded"] == ["L0", "L1"]
    assert "## Context layers loaded: [L0, L1]" in layered_context
    assert "### L0 Identity" in layered_context
    assert "### L1 Essential Story" in layered_context
    assert count_tokens(layered_context) <= 1200


@pytest.mark.asyncio
async def test_context_resource_appends_l2_when_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_shared_files(tmp_path)
    plans = tmp_path / ".cortex" / "plans"
    _ = plans.mkdir(parents=True)
    _ = (plans / "topic-a.md").write_text(
        "# Topic A\n\nOn-demand details", encoding="utf-8"
    )

    monkeypatch.setattr(
        "cortex.core.session_config.read_session_config",
        lambda: {
            "task_description": "general session context",
            "context_layers": ["l0", "l1", "l2"],
            "context_topic": "topic-a",
        },
    )
    _patch_context_runtime(monkeypatch, tmp_path)
    handlers.invalidate_context_resource_cache()

    payload = json.loads(await handlers.load_context())
    layered_context = str(payload["layered_context"])
    assert "### L2 On-Demand" in layered_context
    assert "On-demand details" in layered_context
