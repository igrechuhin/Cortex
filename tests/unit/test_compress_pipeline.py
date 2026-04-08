"""Unit tests for single-file compression pipeline."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

from pytest import MonkeyPatch

from cortex.tools.compress.compress import compress_file


def _original_markdown() -> str:
    return """# Guide
## Steps
- keep this bullet
Path: .cortex/synapse/prompts/plan.md
URL: https://example.com/docs
```python
print("hello")
```"""


def _compressed_valid() -> str:
    return """# Guide
## Steps
- keep bullet
Path: .cortex/synapse/prompts/plan.md
URL: https://example.com/docs
```python
print("hello")
```"""


def _compressed_invalid() -> str:
    return """# Guide
## Steps
- keep this bullet
Path: .cortex/synapse/prompts/plan.md
```python
print("hello")
```"""


def _ok_process(stdout: str) -> CompletedProcess[str]:
    return CompletedProcess(
        args=["claude", "--print"], returncode=0, stdout=stdout, stderr=""
    )


def test_compress_file_happy_path(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    # Arrange
    target = tmp_path / "notes.md"
    original = _original_markdown()
    _ = target.write_text(original, encoding="utf-8")

    def fake_run(
        command: list[str], *, input: str, capture_output: bool, text: bool, check: bool
    ) -> CompletedProcess[str]:
        return _ok_process(_compressed_valid())

    monkeypatch.setattr("cortex.tools.compress.compress.subprocess.run", fake_run)

    # Act
    result = compress_file(target)

    # Assert
    assert result.success is True
    assert result.token_ratio is not None
    assert result.backup_path == target.with_suffix(".md.original")
    assert target.read_text(encoding="utf-8").rstrip() == _compressed_valid().rstrip()
    assert result.backup_path is not None
    assert result.backup_path.read_text(encoding="utf-8") == original


def test_compress_file_validation_fail_then_success(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Arrange
    target = tmp_path / "notes.md"
    _ = target.write_text(_original_markdown(), encoding="utf-8")
    outputs = [_compressed_invalid(), _compressed_valid()]

    def fake_run(
        command: list[str], *, input: str, capture_output: bool, text: bool, check: bool
    ) -> CompletedProcess[str]:
        output = outputs.pop(0)
        return _ok_process(output)

    monkeypatch.setattr("cortex.tools.compress.compress.subprocess.run", fake_run)

    # Act
    result = compress_file(target)

    # Assert
    assert result.success is True
    assert result.errors == []
    assert target.read_text(encoding="utf-8").rstrip() == _compressed_valid().rstrip()
    assert outputs == []


def test_compress_file_retries_exhausted_restores_backup(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Arrange
    target = tmp_path / "notes.md"
    original = _original_markdown()
    _ = target.write_text(original, encoding="utf-8")

    def fake_run(
        command: list[str], *, input: str, capture_output: bool, text: bool, check: bool
    ) -> CompletedProcess[str]:
        return _ok_process(_compressed_invalid())

    monkeypatch.setattr("cortex.tools.compress.compress.subprocess.run", fake_run)

    # Act
    result = compress_file(target)

    # Assert
    assert result.success is False
    assert result.errors != []
    assert result.backup_path == target.with_suffix(".md.original")
    assert target.read_text(encoding="utf-8").rstrip() == original.rstrip()
    assert result.backup_path is not None
    assert result.backup_path.read_text(encoding="utf-8") == original


def test_compress_file_dry_run_does_not_write_files(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Arrange
    target = tmp_path / "notes.md"
    original = _original_markdown()
    _ = target.write_text(original, encoding="utf-8")

    def fake_run(
        command: list[str], *, input: str, capture_output: bool, text: bool, check: bool
    ) -> CompletedProcess[str]:
        return _ok_process(_compressed_valid())

    monkeypatch.setattr("cortex.tools.compress.compress.subprocess.run", fake_run)

    # Act
    result = compress_file(target, dry_run=True)

    # Assert
    assert result.success is True
    assert result.backup_path is None
    assert target.read_text(encoding="utf-8") == original
    assert not target.with_suffix(".md.original").exists()


def test_compress_file_falls_back_when_claude_unavailable(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Arrange — include removable filler phrases so the safe fallback reduces tokens.
    target = tmp_path / "notes.md"
    original = """# Guide
## Steps
- Please note that it is important to keep this bullet in order to satisfy the guide.
Path: .cortex/synapse/prompts/plan.md
URL: https://example.com/docs
```python
print("hello")
```"""
    _ = target.write_text(original, encoding="utf-8")

    def fake_run(
        command: list[str], *, input: str, capture_output: bool, text: bool, check: bool
    ) -> CompletedProcess[str]:
        return CompletedProcess(
            args=["claude", "--print"],
            returncode=1,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr("cortex.tools.compress.compress.subprocess.run", fake_run)

    # Act
    result = compress_file(target)

    # Assert
    assert result.success is True
    assert result.token_ratio is not None
    assert result.token_ratio < 1
    assert result.backup_path == target.with_suffix(".md.original")
