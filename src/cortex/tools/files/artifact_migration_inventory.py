"""Bounded authored Markdown inventory, separate from strict payload discovery."""

import os
import subprocess
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.completion_transaction_io import validate_contained_path

_SKIP_DIRS = frozenset(
    {
        ".git",
        ".build",
        ".swiftpm",
        "build",
        "build.rollback",
        "deriveddata",
        "derived",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".cache",
        ".serena",
        ".pytest_cache",
        ".ruff_cache",
        ".rumdl_cache",
        ".codegraph",
        ".sourcekit-lsp",
        "xcuserdata",
        "pods",
        "carthage",
    }
)
_PACKAGE_SUFFIXES = (
    ".framework",
    ".xcframework",
    ".app",
    ".bundle",
    ".dsym",
    ".xcodeproj",
    ".xcworkspace",
)
_SKIP_ROOTS = (
    ".cortex/skills",
    ".agents/skills",
    ".claude/skills",
    ".cortex/.session",
    ".cortex/synapse",
    ".cortex/rules",
    ".cortex/wal",
    ".cortex/history",
    ".cortex/.runs",
    ".cortex/experience/artifacts",
    "ModelTraining/Outputs",
    "Sources",
    "Tests",
    "src",
    "tests",
    "Plugins",
    "Code",
    "code",
    "Data",
)


def _excluded(root: Path, path: Path) -> bool:
    """Apply lexical exclusions before inspecting any generated or code pointer."""
    parts = path.relative_to(root).parts
    return any(
        part.casefold() in _SKIP_DIRS or part.casefold().endswith(_PACKAGE_SUFFIXES)
        for part in parts
    ) or any(path.is_relative_to(root / relative) for relative in _SKIP_ROOTS)


def _walk_markdown(root: Path, anchor: Path) -> list[Path]:
    """Walk only reference-eligible directories, never following directory links."""
    validate_contained_path(anchor, root)
    if not anchor.exists():
        return []
    result: list[Path] = []
    for directory, directories, names in os.walk(anchor, followlinks=False):
        directories[:] = sorted(
            name for name in directories if not _excluded(root, Path(directory) / name)
        )
        result.extend(
            Path(directory) / name
            for name in names
            if name.lower().endswith(".md")
            and not _excluded(root, Path(directory) / name)
        )
    return result


def _git_markdown(root: Path) -> list[Path]:
    """Use native repository ignore rules for tracked and untracked authored files."""
    try:
        process = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                ":(icase,glob)**/*.md",
            ],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError(f"Cannot inventory authored Markdown: {error}") from error
    if process.returncode:
        raise ValueError(
            "Cannot inventory authored Markdown: " + os.fsdecode(process.stderr).strip()
        )
    return [root / os.fsdecode(value) for value in process.stdout.split(b"\0") if value]


def reference_files(root: Path) -> list[Path]:
    """Inventory eligible authored files, including gitignored Cortex references."""
    cortex = get_cortex_path(root, CortexResourceType.CORTEX_DIR)
    candidates = _walk_markdown(root, cortex)
    candidates.extend(
        _git_markdown(root) if (root / ".git").exists() else _walk_markdown(root, root)
    )
    result: list[Path] = []
    for path in sorted(set(candidates)):
        if _excluded(root, path):
            continue
        validate_contained_path(path, root)
        if not path.exists():
            continue
        if not path.is_file():
            raise ValueError(f"Not a regular Markdown input: {path}")
        result.append(path)
    return result
