"""Tests for language_scripts_scaffolding — stub creation for non-Python languages."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from cortex.structure.language_scripts_scaffolding import (
    build_missing_native_script_warnings,
    scaffold_language_scripts,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scripts_dir(tmp_path: Path, language: str) -> Path:
    return tmp_path / ".cortex" / "synapse" / "scripts" / language


def _assert_stub_exists(scripts_dir: Path, *, executable: bool = True) -> None:
    readme = scripts_dir / "README.md"
    script = scripts_dir / "run_quality_check.sh"
    assert readme.exists(), f"README.md missing in {scripts_dir}"
    assert script.exists(), f"run_quality_check.sh missing in {scripts_dir}"
    if executable:
        mode = script.stat().st_mode
        assert mode & stat.S_IXUSR, "run_quality_check.sh is not user-executable"


# ---------------------------------------------------------------------------
# Python / Swift — native scripts; stubs must NOT be created
# ---------------------------------------------------------------------------


class TestNativeLanguagesSkipped:
    def test_python_is_skipped(self, tmp_path: Path) -> None:
        """scaffold_language_scripts creates nothing for python (native scripts exist)."""
        result = scaffold_language_scripts(tmp_path, ["python"])

        assert result == []
        assert not _scripts_dir(tmp_path, "python").exists()

    def test_swift_is_skipped(self, tmp_path: Path) -> None:
        """scaffold_language_scripts creates nothing for swift (native scripts exist)."""
        result = scaffold_language_scripts(tmp_path, ["swift"])

        assert result == []
        assert not _scripts_dir(tmp_path, "swift").exists()

    def test_empty_language_list_returns_empty(self, tmp_path: Path) -> None:
        result = scaffold_language_scripts(tmp_path, [])

        assert result == []


# ---------------------------------------------------------------------------
# Java
# ---------------------------------------------------------------------------


class TestJavaScaffolding:
    def test_creates_readme_and_script(self, tmp_path: Path) -> None:
        """scaffold_language_scripts creates README.md and run_quality_check.sh for java."""
        result = scaffold_language_scripts(tmp_path, ["java"])

        scripts_dir = _scripts_dir(tmp_path, "java")
        _assert_stub_exists(scripts_dir)
        assert len(result) == 2
        assert any("README.md" in p for p in result)
        assert any("run_quality_check.sh" in p for p in result)

    def test_readme_contains_java_hints(self, tmp_path: Path) -> None:
        _ = scaffold_language_scripts(tmp_path, ["java"])

        readme = (_scripts_dir(tmp_path, "java") / "README.md").read_text(
            encoding="utf-8"
        )
        assert "java" in readme.lower()
        assert "gradle" in readme.lower()
        assert "maven" in readme.lower()

    def test_script_has_shebang_and_set_euo(self, tmp_path: Path) -> None:
        _ = scaffold_language_scripts(tmp_path, ["java"])

        script = (_scripts_dir(tmp_path, "java") / "run_quality_check.sh").read_text(
            encoding="utf-8"
        )
        assert script.startswith("#!/usr/bin/env bash")
        assert "set -euo pipefail" in script

    def test_idempotent_when_files_already_exist(self, tmp_path: Path) -> None:
        """Second call does not overwrite existing files and returns empty list."""
        _ = scaffold_language_scripts(tmp_path, ["java"])
        original_readme = (_scripts_dir(tmp_path, "java") / "README.md").read_text(
            encoding="utf-8"
        )

        result2 = scaffold_language_scripts(tmp_path, ["java"])

        assert result2 == []
        assert (_scripts_dir(tmp_path, "java") / "README.md").read_text(
            encoding="utf-8"
        ) == original_readme


# ---------------------------------------------------------------------------
# Go
# ---------------------------------------------------------------------------


class TestGoScaffolding:
    def test_creates_readme_and_script(self, tmp_path: Path) -> None:
        result = scaffold_language_scripts(tmp_path, ["go"])

        _assert_stub_exists(_scripts_dir(tmp_path, "go"))
        assert len(result) == 2

    def test_readme_mentions_go_commands(self, tmp_path: Path) -> None:
        _ = scaffold_language_scripts(tmp_path, ["go"])

        readme = (_scripts_dir(tmp_path, "go") / "README.md").read_text(
            encoding="utf-8"
        )
        assert "go build" in readme
        assert "go test" in readme

    def test_quality_script_contains_go_commands(self, tmp_path: Path) -> None:
        _ = scaffold_language_scripts(tmp_path, ["go"])

        script = (_scripts_dir(tmp_path, "go") / "run_quality_check.sh").read_text(
            encoding="utf-8"
        )
        assert "go build ./..." in script
        assert "go test ./..." in script


# ---------------------------------------------------------------------------
# Rust
# ---------------------------------------------------------------------------


class TestRustScaffolding:
    def test_creates_readme_and_script(self, tmp_path: Path) -> None:
        result = scaffold_language_scripts(tmp_path, ["rust"])

        _assert_stub_exists(_scripts_dir(tmp_path, "rust"))
        assert len(result) == 2

    def test_readme_mentions_cargo_commands(self, tmp_path: Path) -> None:
        _ = scaffold_language_scripts(tmp_path, ["rust"])

        readme = (_scripts_dir(tmp_path, "rust") / "README.md").read_text(
            encoding="utf-8"
        )
        assert "cargo build" in readme
        assert "cargo test" in readme

    def test_quality_script_contains_cargo_commands(self, tmp_path: Path) -> None:
        _ = scaffold_language_scripts(tmp_path, ["rust"])

        script = (_scripts_dir(tmp_path, "rust") / "run_quality_check.sh").read_text(
            encoding="utf-8"
        )
        assert "cargo build" in script
        assert "cargo test" in script


# ---------------------------------------------------------------------------
# TypeScript
# ---------------------------------------------------------------------------


class TestTypeScriptScaffolding:
    def test_creates_readme_and_script(self, tmp_path: Path) -> None:
        result = scaffold_language_scripts(tmp_path, ["typescript"])

        _assert_stub_exists(_scripts_dir(tmp_path, "typescript"))
        assert len(result) == 2

    def test_readme_mentions_npm_commands(self, tmp_path: Path) -> None:
        _ = scaffold_language_scripts(tmp_path, ["typescript"])

        readme = (_scripts_dir(tmp_path, "typescript") / "README.md").read_text(
            encoding="utf-8"
        )
        assert "npm run build" in readme
        assert "npm test" in readme

    def test_quality_script_contains_npm_commands(self, tmp_path: Path) -> None:
        _ = scaffold_language_scripts(tmp_path, ["typescript"])

        script = (
            _scripts_dir(tmp_path, "typescript") / "run_quality_check.sh"
        ).read_text(encoding="utf-8")
        assert "npm run build" in script
        assert "npm test" in script


# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------


class TestJavaScriptScaffolding:
    def test_creates_readme_and_script(self, tmp_path: Path) -> None:
        result = scaffold_language_scripts(tmp_path, ["javascript"])

        _assert_stub_exists(_scripts_dir(tmp_path, "javascript"))
        assert len(result) == 2

    def test_readme_mentions_npm_commands(self, tmp_path: Path) -> None:
        _ = scaffold_language_scripts(tmp_path, ["javascript"])

        readme = (_scripts_dir(tmp_path, "javascript") / "README.md").read_text(
            encoding="utf-8"
        )
        assert "npm run build" in readme
        assert "npm test" in readme


# ---------------------------------------------------------------------------
# Multiple languages in one call
# ---------------------------------------------------------------------------


class TestMultipleLanguages:
    def test_scaffolds_all_non_native_languages(self, tmp_path: Path) -> None:
        """All five non-native languages get stubs in a single call."""
        languages = ["java", "go", "rust", "typescript", "javascript"]
        result = scaffold_language_scripts(tmp_path, languages)

        # 2 files per language × 5 languages = 10
        assert len(result) == 10
        for lang in languages:
            _assert_stub_exists(_scripts_dir(tmp_path, lang))

    def test_mixed_native_and_non_native(self, tmp_path: Path) -> None:
        """Python and Swift are skipped; other languages are scaffolded."""
        result = scaffold_language_scripts(tmp_path, ["python", "java", "swift", "go"])

        java_dir = _scripts_dir(tmp_path, "java")
        go_dir = _scripts_dir(tmp_path, "go")
        _assert_stub_exists(java_dir)
        _assert_stub_exists(go_dir)
        assert not _scripts_dir(tmp_path, "python").exists()
        assert not _scripts_dir(tmp_path, "swift").exists()
        # 2 files for java + 2 files for go
        assert len(result) == 4

    def test_idempotent_across_multiple_calls(self, tmp_path: Path) -> None:
        """Second call with same languages returns empty list (no overwrites)."""
        languages = ["go", "rust"]
        _ = scaffold_language_scripts(tmp_path, languages)

        result2 = scaffold_language_scripts(tmp_path, languages)

        assert result2 == []

    def test_partial_idempotency(self, tmp_path: Path) -> None:
        """Second call only creates files not yet present."""
        _ = scaffold_language_scripts(tmp_path, ["go"])
        result2 = scaffold_language_scripts(tmp_path, ["go", "rust"])

        # Only rust's 2 files should be new
        assert len(result2) == 2
        assert all("rust" in p for p in result2)


# ---------------------------------------------------------------------------
# Return value structure
# ---------------------------------------------------------------------------


class TestReturnValues:
    def test_returned_paths_are_absolute_strings(self, tmp_path: Path) -> None:
        result = scaffold_language_scripts(tmp_path, ["go"])

        assert all(Path(p).is_absolute() for p in result)

    def test_returned_paths_point_to_existing_files(self, tmp_path: Path) -> None:
        result = scaffold_language_scripts(tmp_path, ["rust"])

        assert all(Path(p).exists() for p in result)

    def test_script_is_executable(self, tmp_path: Path) -> None:
        """run_quality_check.sh has user-executable bit set."""
        _ = scaffold_language_scripts(tmp_path, ["go"])

        script = _scripts_dir(tmp_path, "go") / "run_quality_check.sh"
        mode = script.stat().st_mode
        assert mode & stat.S_IXUSR


# ---------------------------------------------------------------------------
# Unknown language fallback
# ---------------------------------------------------------------------------


class TestUnknownLanguage:
    def test_unknown_language_gets_generic_stub(self, tmp_path: Path) -> None:
        """An unrecognised language key still gets README + script stubs."""
        result = scaffold_language_scripts(tmp_path, ["elixir"])

        scripts_dir = _scripts_dir(tmp_path, "elixir")
        assert scripts_dir.exists()
        assert (scripts_dir / "README.md").exists()
        assert (scripts_dir / "run_quality_check.sh").exists()
        assert len(result) == 2

    def test_unknown_language_script_has_todo_comment(self, tmp_path: Path) -> None:
        _ = scaffold_language_scripts(tmp_path, ["elixir"])

        script = (_scripts_dir(tmp_path, "elixir") / "run_quality_check.sh").read_text(
            encoding="utf-8"
        )
        assert "quality-check command" in script


class TestScaffoldingWarnings:
    def test_warnings_include_non_native_languages_only(self, tmp_path: Path) -> None:
        warnings = build_missing_native_script_warnings(
            tmp_path, ["python", "swift", "typescript", "go"]
        )

        assert len(warnings) == 2
        assert "typescript" in warnings[0]
        assert "go" in warnings[1]
        assert "run_quality_check.sh" in warnings[0]
        assert "run_quality_check.sh" in warnings[1]

    def test_warnings_empty_for_native_languages(self, tmp_path: Path) -> None:
        warnings = build_missing_native_script_warnings(tmp_path, ["python", "swift"])
        assert warnings == []


# ---------------------------------------------------------------------------
# Kotlin — explicit language pack
# ---------------------------------------------------------------------------


class TestKotlinScaffolding:
    def test_creates_readme_and_script(self, tmp_path: Path) -> None:
        """scaffold_language_scripts creates README.md and run_quality_check.sh for kotlin."""
        result = scaffold_language_scripts(tmp_path, ["kotlin"])

        scripts_dir = _scripts_dir(tmp_path, "kotlin")
        _assert_stub_exists(scripts_dir)
        assert len(result) == 2

    def test_readme_mentions_gradle_kotlin_dsl(self, tmp_path: Path) -> None:
        _ = scaffold_language_scripts(tmp_path, ["kotlin"])

        readme = (_scripts_dir(tmp_path, "kotlin") / "README.md").read_text(
            encoding="utf-8"
        )
        assert "kotlin" in readme.lower()
        assert "gradle kotlin dsl" in readme.lower()

    def test_quality_script_contains_gradle_example(self, tmp_path: Path) -> None:
        _ = scaffold_language_scripts(tmp_path, ["kotlin"])

        script = (_scripts_dir(tmp_path, "kotlin") / "run_quality_check.sh").read_text(
            encoding="utf-8"
        )
        assert "./gradlew build test" in script


# ---------------------------------------------------------------------------
# C# — explicit language pack
# ---------------------------------------------------------------------------


class TestCSharpScaffolding:
    def test_creates_readme_and_script(self, tmp_path: Path) -> None:
        result = scaffold_language_scripts(tmp_path, ["csharp"])

        _assert_stub_exists(_scripts_dir(tmp_path, "csharp"))
        assert len(result) == 2

    def test_readme_mentions_dotnet_commands(self, tmp_path: Path) -> None:
        _ = scaffold_language_scripts(tmp_path, ["csharp"])

        readme = (_scripts_dir(tmp_path, "csharp") / "README.md").read_text(
            encoding="utf-8"
        )
        assert "dotnet build" in readme
        assert "dotnet test" in readme

    def test_quality_script_contains_dotnet_commands(self, tmp_path: Path) -> None:
        _ = scaffold_language_scripts(tmp_path, ["csharp"])

        script = (_scripts_dir(tmp_path, "csharp") / "run_quality_check.sh").read_text(
            encoding="utf-8"
        )
        assert "dotnet build" in script
        assert "dotnet test" in script


# ---------------------------------------------------------------------------
# Regression: Swift stubs were previously always emitted (old implementation)
# ---------------------------------------------------------------------------


class TestSwiftRegressionNotScaffolded:
    @pytest.mark.parametrize("lang", ["swift", "python"])
    def test_native_language_never_gets_stub(self, tmp_path: Path, lang: str) -> None:
        result = scaffold_language_scripts(tmp_path, [lang])

        assert result == []
        assert not _scripts_dir(tmp_path, lang).exists()
