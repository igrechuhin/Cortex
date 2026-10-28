"""Direct script API coverage complements subprocess-consumer regressions."""

import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from tests.helpers.spelling_fixtures import (
    REPOSITORY_ROOT,
    SPELLING_CASES,
    cleanup_checker,
    configure_checker,
)


def _checker() -> Callable[[list[Path], Path], tuple[int, str]]:
    script = REPOSITORY_ROOT / ".cortex/synapse/scripts/python/check_spelling.py"
    namespace = runpy.run_path(str(script))
    return cast(
        Callable[[list[Path], Path], tuple[int, str]],
        namespace["check_spelling_with_cspell"],
    )


@pytest.mark.parametrize(("mode", "success", "diagnostic"), SPELLING_CASES)
def test_script_api_preserves_checker_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    success: bool,
    diagnostic: str,
) -> None:
    # Arrange: use the same executable faults as the real consumer tests.
    configure_checker(tmp_path, mode, monkeypatch)
    checker = _checker()
    try:
        # Act: load the real canonical script, not a fixture copy or mock.
        status, output = checker([tmp_path / "subject.py"], tmp_path)
        # Assert: success is status-only; diagnostic parsing cannot change it.
        assert (status == 0) is success
        if not success and mode != "signal":
            assert diagnostic in output
        if mode == "signal":
            assert status == -15
    finally:
        cleanup_checker(tmp_path)


@pytest.mark.parametrize(
    "variable", ["SPELL_CHECKER_TIMEOUT", "SPELL_CHECKER_PREFLIGHT_TIMEOUT"]
)
@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "invalid"])
def test_script_api_rejects_invalid_bounds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    # Arrange.
    configure_checker(tmp_path, "success", monkeypatch)
    monkeypatch.setenv(variable, value)
    # Act.
    status, output = _checker()([tmp_path / "subject.py"], tmp_path)
    # Assert.
    assert status != 0
    assert "Error configuring spell checker" in output


@pytest.mark.parametrize("command", ["", "  ", "'unterminated"])
def test_script_api_rejects_invalid_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    # Arrange.
    monkeypatch.setenv("SPELL_CHECKER_CMD", command)
    # Act.
    status, output = _checker()([tmp_path / "subject.py"], tmp_path)
    # Assert.
    assert status != 0
    assert "Error configuring spell checker" in output


def test_script_api_empty_selection_does_not_start_checker(tmp_path: Path) -> None:
    # Arrange / Act / Assert: preserve the existing empty-selection contract.
    assert _checker()([], tmp_path) == (0, "")
