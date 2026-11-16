"""Approve the locked installed Markdown executable without invoking a tool manager."""

import base64
import csv
import hashlib
import io
import os
import stat
import sys
from email.parser import Parser
from pathlib import Path

from cortex.core.path_resolver import ProjectResourceType, get_project_path

APPROVED_RUMDL_VERSION = "0.1.45"
_MAX_METADATA_BYTES = 131072
_MAX_EXECUTABLE_BYTES = 67108864


class MarkdownToolError(ValueError):
    """No usable installed tool can satisfy the packaged approval contract."""


def approved_environments(root: Path | None) -> tuple[Path, ...]:
    """Only the attached project's environments and the running package environment."""
    candidates = [Path(sys.prefix)]
    if root is not None:
        candidates = [
            get_project_path(root, ProjectResourceType.VENV),
            get_project_path(root, ProjectResourceType.LEGACY_VENV),
            *candidates,
        ]
    return tuple(dict.fromkeys(candidate.resolve() for candidate in candidates))


def _metadata_directories(environment: Path) -> list[Path]:
    sites = [environment / "Lib" / "site-packages"]
    sites.extend(sorted((environment / "lib").glob("python*/site-packages"))[:8])
    return [
        location
        for site in sites
        for location in sorted(site.glob("rumdl-*.dist-info"))[:8]
        if location.resolve().is_relative_to(environment)
    ]


def _read_bounded(path: Path, maximum: int) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise MarkdownToolError("installed_file_unsafe")
        content = stream.read(maximum + 1)
    if len(content) > maximum:
        raise MarkdownToolError("installed_file_too_large")
    return content


def _validate_metadata(directory: Path) -> None:
    metadata = Parser().parsestr(
        _read_bounded(directory / "METADATA", _MAX_METADATA_BYTES).decode("utf-8")
    )
    if metadata.get("Name") != "rumdl":
        raise MarkdownToolError("metadata_name_mismatch")
    if metadata.get("Version") != APPROVED_RUMDL_VERSION:
        raise MarkdownToolError("metadata_version_mismatch")


def _record_entry(
    directory: Path, executable: Path, environment: Path
) -> tuple[str, int]:
    text = _read_bounded(directory / "RECORD", _MAX_METADATA_BYTES).decode("utf-8")
    matches: list[tuple[str, int]] = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) != 3:
            raise MarkdownToolError("record_invalid")
        path, digest, raw_size = row
        located = (directory.parent / path).resolve()
        if located != executable:
            continue
        if not located.is_relative_to(environment) or not raw_size.isdecimal():
            raise MarkdownToolError("record_path_or_size_invalid")
        matches.append((digest, int(raw_size)))
    if len(matches) != 1:
        raise MarkdownToolError("executable_record_missing_or_ambiguous")
    return matches[0]


def _validate_executable(directory: Path, environment: Path) -> Path:
    name = "Scripts/rumdl.exe" if os.name == "nt" else "bin/rumdl"
    executable = (environment / name).resolve()
    if not executable.is_relative_to(environment) or not os.access(executable, os.X_OK):
        raise MarkdownToolError("executable_unavailable_or_unsafe")
    digest, size = _record_entry(directory, executable, environment)
    content = _read_bounded(executable, _MAX_EXECUTABLE_BYTES)
    actual = "sha256=" + base64.urlsafe_b64encode(
        hashlib.sha256(content).digest()
    ).decode().rstrip("=")
    if digest != actual or size != len(content):
        raise MarkdownToolError("executable_record_mismatch")
    return executable


def resolve_approved_rumdl(root: Path | None = None) -> Path:
    """Select a verified installed executable before launching anything."""
    reasons: set[str] = set()
    for environment in approved_environments(root):
        directories = _metadata_directories(environment)
        if not directories:
            reasons.add("metadata_missing")
        for directory in directories:
            try:
                _validate_metadata(directory)
                return _validate_executable(directory, environment)
            except MarkdownToolError as exc:
                reasons.add(str(exc))
            except (OSError, UnicodeError, csv.Error, ValueError):
                reasons.add("installed_provenance_unavailable")
    detail = ", ".join(sorted(reasons)) or "metadata_missing"
    raise MarkdownToolError(
        f"No approved rumdl {APPROVED_RUMDL_VERSION} is usable ({detail}); restore the locked project or Cortex package environment."
    )
