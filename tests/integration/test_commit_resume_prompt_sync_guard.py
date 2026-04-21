"""Guards to keep commit resume-check blocks synchronized."""

from __future__ import annotations

import re
from pathlib import Path

from tests.integration.conftest import synapse_path


def _agent_file(name: str) -> Path:
    return synapse_path() / "cursor-agents" / name


def _resume_check_block(content: str) -> str:
    marker = "## Resume Check (required)"
    start = content.find(marker)
    assert start >= 0, f"Missing resume-check section marker: {marker}"
    mark_running = (
        "Immediately before Step 1, call " '`pipeline_handoff(operation="mark_running"'
    )
    end_marker = content.find(mark_running, start)
    assert end_marker >= 0, "Missing mark_running instruction in resume-check section"
    end_line = content.find("\n", end_marker)
    end = len(content) if end_line < 0 else end_line
    return content[start:end].strip()


def _normalize_resume_block(block: str) -> str:
    normalized = re.sub(r"phases\.[a-zA-Z0-9_-]+", "phases.<phase>", block)
    normalized = re.sub(r'phase="[a-zA-Z0-9_-]+"', 'phase="<phase>"', normalized)
    return normalized


def test_commit_agent_resume_check_blocks_stay_synchronized() -> None:
    """Resume-check docs should only differ by phase token."""
    files = [
        "commit-preflight.md",
        "commit-phase-a.md",
        "commit-phase-b.md",
        "commit-phase-c.md",
        "commit-final-gate.md",
    ]
    normalized_blocks: list[str] = []
    for file_name in files:
        content = _agent_file(file_name).read_text(encoding="utf-8")
        block = _resume_check_block(content)
        normalized_blocks.append(_normalize_resume_block(block))

    baseline = normalized_blocks[0]
    for idx, block in enumerate(normalized_blocks[1:], start=1):
        assert block == baseline, f"Resume check block drifted in {files[idx]}"


def test_fix_agent_resume_check_blocks_stay_synchronized() -> None:
    """Fix-agent resume-check docs should only differ by phase token."""
    files = [
        "fix-quality.md",
        "fix-tests.md",
        "fix-coverage.md",
        "fix-docs.md",
    ]
    normalized_blocks: list[str] = []
    for file_name in files:
        content = _agent_file(file_name).read_text(encoding="utf-8")
        block = _resume_check_block(content)
        normalized_blocks.append(_normalize_resume_block(block))

    baseline = normalized_blocks[0]
    for idx, block in enumerate(normalized_blocks[1:], start=1):
        assert block == baseline, f"Resume check block drifted in {files[idx]}"
