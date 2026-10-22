"""Disposable, real-file fixtures for revision-bound context resource reads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from cortex.tools.context.scoped_task_state import ScopedTaskState
from cortex.tools.context.source_revision import SourceRevision
from cortex.tools.optimization import handlers


def write_source(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(text, encoding="utf-8")
    return path


def write_plan(
    root: Path,
    slug: str = "selected",
    status: str = "PENDING",
    dependencies: list[str] | None = None,
    goal: str = "Implement selected feature.",
) -> Path:
    return write_source(
        root,
        f".cortex/plans/{slug}.md",
        f"---\nstatus: {status}\ndepends_on: {json.dumps(dependencies or [])}\n---\n"
        + f"## Goal\n{goal}\n\n## Scope\n**out_of_scope**\n- No deployment.\n",
    )


def scoped_packet(payload: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], payload["scoped_context"])


def task_state(payload: dict[str, object]) -> ScopedTaskState:
    return ScopedTaskState.model_validate(scoped_packet(payload)["task_state"])


def manifest(payload: dict[str, object]) -> dict[str, SourceRevision]:
    entries = cast(list[object], scoped_packet(payload)["revision_manifest"])
    sources = [SourceRevision.model_validate(item) for item in entries]
    return {source.identity: source for source in sources}


class ScopedResourceHarness:
    """Only substitute optimizer selection; exercise actual source readers/cache/budget."""

    def __init__(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.root = root
        self.config: dict[str, object] = {
            "scope": "plan:selected",
            "task_description": "Implement selected feature",
            "token_budget": 20000,
        }
        self.calls = 0
        _ = write_plan(root)
        self.rule = write_source(
            root, ".cortex/rules/selected.mdc", "## Universal\nKeep selected rules.\n"
        )
        handlers.invalidate_context_resource_cache()
        monkeypatch.setattr(
            "cortex.core.session_config.read_session_config", lambda: self.config
        )
        monkeypatch.setattr(handlers, "resolve_project_root_async", self.resolve_root)
        monkeypatch.setattr(handlers, "get_relevant_rules", self.read_rules)
        monkeypatch.setattr(handlers, "load_context_impl", self.load_base)

    async def resolve_root(self, project_root: str | None, ctx: object) -> Path:
        _ = project_root, ctx
        return self.root

    async def read_rules(self) -> str:
        selected: list[dict[str, object]] = []
        if self.rule.is_file():
            selected.append(
                {
                    "file": "selected.mdc",
                    "source": "local",
                    "category": "general",
                    "content": self.rule.read_text(encoding="utf-8"),
                }
            )
        return json.dumps(
            {
                "status": "success",
                "rules": selected,
                "rules_manager_status": {"rules_folder": ".cortex/rules"},
            },
            sort_keys=True,
        )

    async def load_base(self, task_description: str, token_budget: int) -> str:
        self.calls += 1
        return json.dumps(
            {
                "status": "success",
                "task_description": task_description,
                "file_names": [],
                "token_budget": token_budget,
            }
        )

    async def read(self) -> dict[str, object]:
        return cast(dict[str, object], json.loads(await handlers.load_context()))
