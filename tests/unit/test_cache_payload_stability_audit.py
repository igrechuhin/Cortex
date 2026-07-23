"""Unit tests for the prompt-cache payload stability audit.

Covers ``audit_cache_payload_stability()`` (Success Criteria 3 of the
``prompt-cache-payload-stability-for-cached-mcp-resources`` plan) and the
``check_cache_payload_stability()`` file-scanning wrapper wired into the
``quality`` pre-commit check.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.tools.execution.pre_commit_cache_payload_audit import (
    audit_cache_payload_stability,
    check_cache_payload_stability,
)

_STABLE_FIXTURE = """
def build_payload() -> str:
    return json.dumps({"status": "success"}, indent=2)
"""

_VOLATILE_FIXTURES = [
    pytest.param("x = datetime.now()", "datetime.now() call", id="datetime-now"),
    pytest.param("x = time.time()", "time.time() call", id="time-time"),
    pytest.param("x = str(uuid4())", "uuid1()/uuid4() call", id="uuid4"),
    pytest.param("x = str(uuid1())", "uuid1()/uuid4() call", id="uuid1"),
    pytest.param("x = os.getpid()", "os.getpid() call", id="getpid"),
    pytest.param(
        'x = "2026-07-23T10:15:00"', "raw ISO-timestamp literal", id="iso-timestamp"
    ),
]


def test_audit_cache_payload_stability_returns_empty_list_for_stable_fixture() -> None:
    # Arrange / Act
    violations = audit_cache_payload_stability(_STABLE_FIXTURE)

    # Assert
    assert violations == []


@pytest.mark.parametrize("line, expected_label", _VOLATILE_FIXTURES)
def test_audit_cache_payload_stability_flags_each_volatile_pattern(
    line: str, expected_label: str
) -> None:
    # Arrange
    text = f"def build_payload() -> str:\n    {line}\n    return x\n"

    # Act
    violations = audit_cache_payload_stability(text)

    # Assert
    assert len(violations) == 1
    assert expected_label in violations[0]
    assert "line 2" in violations[0]


def test_check_cache_payload_stability_skips_missing_target_files(
    tmp_path: Path,
) -> None:
    # Arrange: empty project root — neither target file exists.
    # Act
    violations = check_cache_payload_stability(tmp_path)

    # Assert
    assert violations == []


def test_check_cache_payload_stability_flags_violation_with_file_prefix(
    tmp_path: Path,
) -> None:
    # Arrange
    handlers = tmp_path / "src" / "cortex" / "tools" / "optimization"
    handlers.mkdir(parents=True)
    _ = (handlers / "handlers.py").write_text(
        "async def load_context() -> str:\n    return str(uuid4())\n",
        encoding="utf-8",
    )

    # Act
    violations = check_cache_payload_stability(tmp_path)

    # Assert
    assert len(violations) == 1
    assert violations[0].startswith("src/cortex/tools/optimization/handlers.py:")


def test_check_cache_payload_stability_current_repo_is_clean() -> None:
    """Regression guard: the real handlers.py/rules_operations.py stay clean."""
    # Arrange
    project_root = Path(__file__).resolve().parents[2]

    # Act
    violations = check_cache_payload_stability(project_root)

    # Assert
    assert violations == []
