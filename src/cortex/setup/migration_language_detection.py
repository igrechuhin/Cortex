from __future__ import annotations

from pathlib import Path

# Project-root filenames that imply Python for migration scaffolding (see module docstring).
_PYTHON_ROOT_MARKER_FILENAMES: tuple[str, ...] = (
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "tox.ini",
    "requirements.txt",
    "Pipfile",
    "Pipfile.lock",
    "poetry.lock",
    "uv.lock",
    "pdm.toml",
    "pdm.lock",
    "pixi.toml",
    "environment.yml",
    "environment.yaml",
    "conda-lock.yml",
    ".python-version",
    "MANIFEST.in",
    "constraints.txt",
    "runtime.txt",
    ".flake8",
    "pytest.ini",
    ".coveragerc",
    "pyrightconfig.json",
    "mypy.ini",
    ".mypy.ini",
    "ruff.toml",
    ".ruff.toml",
    "noxfile.py",
)


def detect_languages_for_migration(project_root: Path) -> list[str]:
    """Detect migration scaffold languages using marker-based priority.

    Priority is aligned with the migration roadmap:
    swift -> typescript/javascript -> java -> csharp -> rust -> go -> python.
    Multiple languages can be returned when multiple markers are present.

    JVM / Java scaffolding uses the shared ``_templates/java/`` pack. Gradle projects
    that only ship Kotlin DSL files (``build.gradle.kts``, ``settings.gradle.kts``),
    Groovy ``settings.gradle`` (without a root ``build.gradle``), or a Gradle wrapper
    (``gradlew`` / ``gradlew.bat``) or Gradle Wrapper metadata
    (``gradle/wrapper/gradle-wrapper.properties``), and Maven projects that ship only the Maven
    wrapper scripts (``mvnw`` / ``mvnw.cmd``) or Maven Wrapper metadata
    (``.mvn/wrapper/maven-wrapper.properties``), are treated as JVM for that purpose.

    Python uses ``pyproject.toml``, ``setup.py``, ``setup.cfg`` (setuptools / legacy
    packaging), ``MANIFEST.in`` (sdist file list), ``constraints.txt`` (pip constraints),
    Heroku ``runtime.txt``, ``.flake8``, ``pytest.ini``, ``.coveragerc``, ``tox.ini``, root ``*.py``,
    static-analysis / task-runner markers ``pyrightconfig.json`` (Pyright),
    ``mypy.ini`` / ``.mypy.ini`` (mypy), ``ruff.toml`` / ``.ruff.toml`` (Ruff), ``noxfile.py`` (Nox),
    Conda ``environment.yml`` / ``environment.yaml``,
    ``conda-lock.yml`` (conda-lock), pyenv-style ``.python-version`` at the repo root,
    or dependency markers ``requirements.txt`` / ``Pipfile``, ``Pipfile.lock``,
    ``poetry.lock``, ``uv.lock``, ``pdm.toml`` / ``pdm.lock`` (PDM), or ``pixi.toml`` (Pixi)
    at the repo root.
    """

    detected: list[str] = []

    if (project_root / "Package.swift").exists():
        detected.append("swift")

    has_package_json = (project_root / "package.json").exists()
    has_tsconfig = (project_root / "tsconfig.json").exists()
    if has_package_json or has_tsconfig:
        if has_tsconfig:
            detected.append("typescript")
        elif has_package_json:
            detected.append("javascript")

    if _has_jvm_migration_markers(project_root):
        detected.append("java")

    if _has_csharp_migration_markers(project_root):
        detected.append("csharp")

    if (project_root / "Cargo.toml").exists():
        detected.append("rust")

    if (project_root / "go.mod").exists():
        detected.append("go")

    if _has_python_sources(project_root):
        detected.append("python")

    return detected


def _has_jvm_migration_markers(project_root: Path) -> bool:
    """True when Maven or Gradle (Groovy or Kotlin DSL, or wrapper) is at the repo root."""
    return (
        (project_root / "pom.xml").exists()
        or (project_root / "build.gradle").exists()
        or (project_root / "build.gradle.kts").exists()
        or (project_root / "settings.gradle").exists()
        or (project_root / "settings.gradle.kts").exists()
        or (project_root / "gradlew").exists()
        or (project_root / "gradlew.bat").exists()
        or (project_root / "gradle" / "wrapper" / "gradle-wrapper.properties").exists()
        or (project_root / "mvnw").exists()
        or (project_root / "mvnw.cmd").exists()
        or (project_root / ".mvn" / "wrapper" / "maven-wrapper.properties").exists()
    )


def _has_csharp_migration_markers(project_root: Path) -> bool:
    """True when a C#/.NET solution or project file is present at the repo root."""
    if any(project_root.glob("*.sln")):
        return True
    return any(project_root.glob("*.csproj"))


def _has_python_sources(project_root: Path) -> bool:
    if any((project_root / name).exists() for name in _PYTHON_ROOT_MARKER_FILENAMES):
        return True
    return bool(list(project_root.glob("*.py")))
