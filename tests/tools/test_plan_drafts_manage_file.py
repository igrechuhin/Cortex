"""Tests for manage_file plan draft listing and discard."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.files.operations import manage_file
from tests.helpers.path_helpers import ensure_test_cortex_structure


async def _call_manage_file_json(
    operation: str, content: str | None = None
) -> dict[str, object]:
    return json.loads(
        await manage_file(
            file_name="activeContext.md",
            operation=operation,
            content=content,
        )
    )


@pytest.mark.asyncio
async def test_manage_file_list_drafts_empty(tmp_path: Path) -> None:
    """list_drafts returns success with zero drafts when plans dir is missing."""
    _ = ensure_test_cortex_structure(tmp_path)
    with patch(
        "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        listed = await _call_manage_file_json("list_drafts")
    assert listed["status"] == "success"
    assert listed["count"] == 0
    assert listed["stale_count"] == 0


@pytest.mark.asyncio
async def test_manage_file_list_and_discard_draft(tmp_path: Path) -> None:
    """list_drafts enumerates draft-*.md; discard_draft removes one by slug."""
    _ = ensure_test_cortex_structure(tmp_path)
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    plans.mkdir(parents=True, exist_ok=True)
    draft = plans / "draft-my-slug.md"
    _ = draft.write_text("---\ntitle: T\n---\n", encoding="utf-8")

    with patch(
        "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        listed = await _call_manage_file_json("list_drafts")
        assert listed["status"] == "success"
        assert listed["count"] == 1
        assert listed["stale_count"] == 0
        drafts = listed.get("drafts")
        assert isinstance(drafts, list) and drafts

        discarded = await _call_manage_file_json(
            "discard_draft", content=json.dumps({"plan_slug": "my-slug"})
        )
        assert discarded["status"] == "success"

        listed_after = await _call_manage_file_json("list_drafts")
        assert listed_after["count"] == 0


@pytest.mark.asyncio
async def test_manage_file_discard_draft_requires_payload(tmp_path: Path) -> None:
    """discard_draft without content returns a validation error."""
    _ = ensure_test_cortex_structure(tmp_path)
    with patch(
        "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        err = await _call_manage_file_json("discard_draft", content=None)
    assert err["status"] == "error"


@pytest.mark.asyncio
async def test_manage_file_list_drafts_marks_stale(tmp_path: Path) -> None:
    """Drafts older than 48h increment stale_count."""
    _ = ensure_test_cortex_structure(tmp_path)
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    plans.mkdir(parents=True, exist_ok=True)
    old_draft = plans / "draft-oldish.md"
    _ = old_draft.write_text("x", encoding="utf-8")
    old_time = time.time() - (50 * 60 * 60)
    os.utime(old_draft, (old_time, old_time))

    with patch(
        "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        listed = await _call_manage_file_json("list_drafts")
    assert listed["stale_count"] == 1
    drafts = listed.get("drafts")
    assert isinstance(drafts, list) and drafts
    first_entry = cast(dict[str, object], drafts[0])
    assert first_entry.get("stale") is True


@pytest.mark.asyncio
async def test_manage_file_list_drafts_without_file_name(tmp_path: Path) -> None:
    """list_drafts works without file_name (file_name not required for draft ops)."""
    _ = ensure_test_cortex_structure(tmp_path)
    with patch(
        "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        result = json.loads(
            await manage_file(
                file_name=None,
                operation="list_drafts",
            )
        )
    assert result["status"] == "success"
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_manage_file_discard_draft_without_file_name(tmp_path: Path) -> None:
    """discard_draft works without file_name and returns validation error when no content."""
    _ = ensure_test_cortex_structure(tmp_path)
    with patch(
        "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        result = json.loads(
            await manage_file(
                file_name=None,
                operation="discard_draft",
                content=None,
            )
        )
    # No file_name should not block discard_draft; content validation fires instead
    assert result["status"] == "error"
    assert "plan_slug" in (result.get("error") or "")
