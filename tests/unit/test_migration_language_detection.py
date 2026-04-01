from __future__ import annotations

from pathlib import Path

import pytest

from cortex.setup.migration_language_detection import detect_languages_for_migration


def test_detect_languages_for_migration_returns_empty_when_no_markers(
    tmp_path: Path,
) -> None:
    assert detect_languages_for_migration(tmp_path) == []


def test_detect_languages_for_migration_detects_python_from_requirements_txt_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "requirements.txt").write_text("requests\n", encoding="utf-8")

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_python_from_pipfile_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "Pipfile").write_text(
        '[packages]\nrequests = "*"\n', encoding="utf-8"
    )

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_python_from_pipfile_lock_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "Pipfile.lock").write_text(
        '{\n  "_meta": {"hash": {"sha256": "x"}}\n}\n',
        encoding="utf-8",
    )

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_python_from_poetry_lock_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "poetry.lock").write_text(
        '[[package]]\nname = "requests"\n',
        encoding="utf-8",
    )

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_python_from_uv_lock_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "uv.lock").write_text(
        'version = 1\nrequires-python = ">=3.11"\n',
        encoding="utf-8",
    )

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_python_from_environment_yml_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "environment.yml").write_text(
        "name: demo\nchannels:\n  - conda-forge\n",
        encoding="utf-8",
    )

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_python_from_environment_yaml_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "environment.yaml").write_text(
        "name: demo\nchannels:\n  - conda-forge\n",
        encoding="utf-8",
    )

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_python_from_conda_lock_yml_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "conda-lock.yml").write_text(
        "metadata:\n  content_hash: {}\n",
        encoding="utf-8",
    )

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_python_from_dot_python_version_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / ".python-version").write_text("3.12.1\n", encoding="utf-8")

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_python_from_manifest_in_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "MANIFEST.in").write_text(
        "include LICENSE\nrecursive-include src *.py\n",
        encoding="utf-8",
    )

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_python_from_constraints_txt_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "constraints.txt").write_text(
        "requests==2.31.0\n",
        encoding="utf-8",
    )

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_python_from_runtime_txt_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "runtime.txt").write_text("python-3.12.1\n", encoding="utf-8")

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_python_from_dot_flake8_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / ".flake8").write_text(
        "[flake8]\nmax-line-length = 100\n",
        encoding="utf-8",
    )

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_python_from_pytest_ini_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "pytest.ini").write_text(
        "[pytest]\ntestpaths = tests\n", encoding="utf-8"
    )

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_python_from_dot_coveragerc_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / ".coveragerc").write_text(
        "[run]\nbranch = True\n", encoding="utf-8"
    )

    assert detect_languages_for_migration(tmp_path) == ["python"]


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("pyrightconfig.json", '{ "include": ["src"] }\n'),
        ("mypy.ini", "[mypy]\n"),
        (".mypy.ini", "[mypy]\n"),
        ("ruff.toml", "[tool.ruff]\nline-length = 100\n"),
        (".ruff.toml", "[tool.ruff]\nline-length = 100\n"),
        ("noxfile.py", "import nox\n\n@nox.session\ndef tests(session):\n    pass\n"),
        (
            "pdm.toml",
            '[project]\nname = "demo"\nversion = "0.1.0"\nrequires-python = ">=3.11"\n',
        ),
        (
            "pdm.lock",
            '# This file is @generated by PDM.\n[[package]]\nname = "demo"\nversion = "1.0.0"\n',
        ),
        (
            "pixi.toml",
            '[project]\nname = "demo"\nchannels = ["conda-forge"]\nplatforms = ["osx-arm64"]\n',
        ),
    ],
)
def test_detect_languages_for_migration_detects_python_from_static_analysis_markers(
    tmp_path: Path,
    filename: str,
    content: str,
) -> None:
    _ = (tmp_path / filename).write_text(content, encoding="utf-8")

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_python_from_setup_cfg_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "setup.cfg").write_text(
        "[metadata]\nname = example\n",
        encoding="utf-8",
    )

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_python_from_tox_ini_only(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "tox.ini").write_text("[tox]\n", encoding="utf-8")

    assert detect_languages_for_migration(tmp_path) == ["python"]


def test_detect_languages_for_migration_detects_swift_first(tmp_path: Path) -> None:
    _ = (tmp_path / "Package.swift").write_text(
        "// swift-tools-version:5.9\nimport PackageDescription\n",
        encoding="utf-8",
    )
    _ = (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='x'\n", encoding="utf-8"
    )

    assert detect_languages_for_migration(tmp_path) == ["swift", "python"]


def test_detect_languages_for_migration_prefers_typescript_over_javascript(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "package.json").write_text('{"name":"x"}\n', encoding="utf-8")
    _ = (tmp_path / "tsconfig.json").write_text("{}\n", encoding="utf-8")

    assert detect_languages_for_migration(tmp_path) == ["typescript"]


def test_detect_languages_for_migration_detects_javascript_when_no_tsconfig(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "package.json").write_text('{"name":"x"}\n', encoding="utf-8")

    assert detect_languages_for_migration(tmp_path) == ["javascript"]


def test_detect_languages_for_migration_detects_java_from_gradle_kotlin_dsl(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "build.gradle.kts").write_text(
        'plugins { kotlin("jvm") }\n', encoding="utf-8"
    )

    assert detect_languages_for_migration(tmp_path) == ["java"]


def test_detect_languages_for_migration_detects_java_from_settings_gradle_kts(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "settings.gradle.kts").write_text(
        'rootProject.name = "app"\n', encoding="utf-8"
    )

    assert detect_languages_for_migration(tmp_path) == ["java"]


def test_detect_languages_for_migration_detects_java_from_settings_gradle_groovy(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "settings.gradle").write_text(
        'rootProject.name = "app"\n', encoding="utf-8"
    )

    assert detect_languages_for_migration(tmp_path) == ["java"]


def test_detect_languages_for_migration_detects_java_from_gradle_wrapper_unix(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "gradlew").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    assert detect_languages_for_migration(tmp_path) == ["java"]


def test_detect_languages_for_migration_detects_java_from_gradle_wrapper_windows(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "gradlew.bat").write_text("@echo off\n", encoding="utf-8")

    assert detect_languages_for_migration(tmp_path) == ["java"]


def test_detect_languages_for_migration_detects_java_from_gradle_wrapper_properties(
    tmp_path: Path,
) -> None:
    props = tmp_path / "gradle" / "wrapper" / "gradle-wrapper.properties"
    _ = props.parent.mkdir(parents=True)
    _ = props.write_text(
        "distributionUrl=https://example.invalid/gradle.zip\n",
        encoding="utf-8",
    )

    assert detect_languages_for_migration(tmp_path) == ["java"]


def test_detect_languages_for_migration_detects_java_from_maven_wrapper_unix(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "mvnw").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    assert detect_languages_for_migration(tmp_path) == ["java"]


def test_detect_languages_for_migration_detects_java_from_maven_wrapper_windows(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "mvnw.cmd").write_text("@echo off\n", encoding="utf-8")

    assert detect_languages_for_migration(tmp_path) == ["java"]


def test_detect_languages_for_migration_detects_java_from_maven_wrapper_properties(
    tmp_path: Path,
) -> None:
    props = tmp_path / ".mvn" / "wrapper" / "maven-wrapper.properties"
    _ = props.parent.mkdir(parents=True)
    _ = props.write_text(
        "distributionUrl=https://example.invalid/maven.zip\n", encoding="utf-8"
    )

    assert detect_languages_for_migration(tmp_path) == ["java"]


def test_detect_languages_for_migration_detects_csharp_from_solution_file(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "Example.sln").write_text(
        "Microsoft Visual Studio Solution File, Format Version 12.00\n",
        encoding="utf-8",
    )

    assert detect_languages_for_migration(tmp_path) == ["csharp"]


def test_detect_languages_for_migration_detects_csharp_from_project_file(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "Example.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
        encoding="utf-8",
    )

    assert detect_languages_for_migration(tmp_path) == ["csharp"]


def test_detect_languages_for_migration_detects_multiple_languages_in_priority_order(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "Package.swift").write_text(
        "// swift-tools-version:5.9\nimport PackageDescription\n",
        encoding="utf-8",
    )
    _ = (tmp_path / "build.gradle").write_text("plugins {}\n", encoding="utf-8")
    _ = (tmp_path / "App.sln").write_text(
        "Microsoft Visual Studio Solution File, Format Version 12.00\n",
        encoding="utf-8",
    )
    _ = (tmp_path / "Cargo.toml").write_text("[package]\nname='x'\n", encoding="utf-8")
    _ = (tmp_path / "go.mod").write_text("module x\n", encoding="utf-8")
    _ = (tmp_path / "main.py").write_text("print('x')\n", encoding="utf-8")

    assert detect_languages_for_migration(tmp_path) == [
        "swift",
        "java",
        "csharp",
        "rust",
        "go",
        "python",
    ]
