"""Shared helpers for pipeline_handoff tool tests."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest


def patch_pipeline_handoff_project_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff.get_or_resolve_project_root",
        AsyncMock(return_value=str(tmp_path)),
    )
