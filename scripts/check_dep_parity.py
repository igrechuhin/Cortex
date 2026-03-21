#!/usr/bin/env python3
"""Validate that [project.dependencies] matches repo-root requirements.txt."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement


def normalize_distribution_name(raw_name: str) -> str:
    """Normalize a distribution name (PEP 503 style: lowercase, underscore to hyphen)."""
    return raw_name.lower().replace("_", "-")


def strip_requirements_txt_line(raw_line: str) -> str | None:
    """Return a non-empty requirement line, or None if blank / comment-only."""
    stripped = raw_line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if " #" in stripped:
        stripped = stripped.split(" #", 1)[0].strip()
    if not stripped or stripped.startswith("#"):
        return None
    return stripped


def parse_requirements_txt(text: str) -> list[str]:
    """Parse requirements.txt: skip blanks and comments; strip inline comments."""
    lines: list[str] = []
    for raw in text.splitlines():
        parsed = strip_requirements_txt_line(raw)
        if parsed is not None:
            lines.append(parsed)
    return lines


def load_pyproject_runtime_dependencies(pyproject_path: Path) -> list[str]:
    """Load [project.dependencies] from pyproject.toml."""
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = data.get("project")
    if not isinstance(project, dict):
        return []
    deps = project.get("dependencies")
    if deps is None:
        return []
    if not isinstance(deps, list):
        msg = f"{pyproject_path}: [project.dependencies] must be a list of strings"
        raise ValueError(msg)
    return [str(item) for item in deps]


def requirement_map(
    requirement_strings: list[str],
    *,
    source_label: str,
) -> dict[str, str]:
    """Map normalized distribution name -> exact requirement string."""
    result: dict[str, str] = {}
    for req_str in requirement_strings:
        try:
            req = Requirement(req_str)
        except InvalidRequirement as exc:
            msg = f"{source_label}: invalid requirement {req_str!r}: {exc}"
            raise ValueError(msg) from exc
        norm = normalize_distribution_name(req.name)
        if norm in result and result[norm] != req_str:
            msg = (
                f"{source_label}: conflicting requirements for {norm!r}: "
                f"{result[norm]!r} vs {req_str!r}"
            )
            raise ValueError(msg)
        result[norm] = req_str
    return result


def collect_mismatches(py_map: dict[str, str], req_map: dict[str, str]) -> list[str]:
    """Describe differences between pyproject and requirements.txt maps."""
    messages: list[str] = []
    for key in sorted(set(py_map) | set(req_map)):
        py_entry = py_map.get(key)
        req_entry = req_map.get(key)
        if py_entry is None:
            messages.append(
                f"Extra in requirements.txt (not in pyproject.toml): {req_entry!r} "
                f"(normalized name: {key})"
            )
        elif req_entry is None:
            messages.append(
                f"Missing from requirements.txt: pyproject.toml has {py_entry!r} "
                f"(normalized name: {key})"
            )
        elif py_entry != req_entry:
            messages.append(
                f"Requirement mismatch for {key}: pyproject.toml {py_entry!r} != "
                f"requirements.txt {req_entry!r}"
            )
    return messages


def check_parity(root: Path) -> list[str]:
    """Return error messages if parity check fails; empty list if OK."""
    pyproject_path = root / "pyproject.toml"
    requirements_path = root / "requirements.txt"
    if not pyproject_path.is_file():
        return [f"Missing pyproject.toml at {pyproject_path}"]
    if not requirements_path.is_file():
        return [f"Missing requirements.txt at {requirements_path}"]

    try:
        py_deps = load_pyproject_runtime_dependencies(pyproject_path)
        req_lines = parse_requirements_txt(requirements_path.read_text(encoding="utf-8"))
        py_map = requirement_map(py_deps, source_label=str(pyproject_path))
        req_map = requirement_map(req_lines, source_label=str(requirements_path))
    except ValueError as exc:
        return [str(exc)]

    return collect_mismatches(py_map, req_map)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify pyproject.toml [project.dependencies] matches requirements.txt.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Directory containing pyproject.toml and requirements.txt (default: cwd)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    mismatches = check_parity(root)
    if mismatches:
        print("Dependency parity check failed:", file=sys.stderr)
        for line in mismatches:
            print(line, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
