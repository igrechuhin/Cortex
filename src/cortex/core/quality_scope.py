"""Ownership boundaries for repository style checks.

Only validated, externally installed skill directories are vendor payloads.
The lock's upstream skillPath never determines a local exclusion path.
"""

from enum import StrEnum
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SKILL_INSTALL_ROOT = Path(".agents") / "skills"
SKILL_LOCK_NAME = "skills-lock.json"


class SkillSourceType(StrEnum):
    """External source types observed in the supported installation manifest."""

    GITHUB = "github"


class InstalledSkill(BaseModel):
    """Validated external provenance; unknown formats remain project-owned."""

    model_config = ConfigDict(extra="ignore")

    source: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    source_type: SkillSourceType = Field(alias="sourceType")
    skill_path: str = Field(alias="skillPath", min_length=1)
    computed_hash: str = Field(alias="computedHash", pattern=r"^[a-f0-9]{64}$")


class SkillLock(BaseModel):
    """Only manifest version one has a supported local installation layout."""

    model_config = ConfigDict(extra="ignore", strict=True)

    version: int = Field(ge=1, le=1)
    skills: dict[str, InstalledSkill]


def _valid_skill_name(name: str) -> bool:
    """Require one installation-directory component, never a path or glob."""
    return (
        bool(name)
        and name[0].isalnum()
        and all(char.isascii() and (char.isalnum() or char in "_-") for char in name)
    )


def _valid_upstream_path(value: str) -> bool:
    """Treat upstream provenance as metadata, rejecting malformed path values."""
    path = PurePosixPath(value)
    return (
        "\\" not in value
        and not path.is_absolute()
        and all(part not in ("", ".", "..") for part in value.split("/"))
        and path.name == "SKILL.md"
    )


def installed_skill_roots(project_root: Path) -> tuple[Path, ...]:
    """Return exact vendor roots; invalid manifests fail closed to normal checks."""
    root = project_root.resolve()
    try:
        lock = SkillLock.model_validate_json((root / SKILL_LOCK_NAME).read_bytes())
    except (OSError, ValidationError):
        return ()
    install_root = root / SKILL_INSTALL_ROOT
    # AI: A symlinked install ancestor must never turn src/ into vendor content.
    if install_root.resolve() != install_root:
        return ()
    return tuple(
        install_root / name
        for name, skill in lock.skills.items()
        if _valid_skill_name(name)
        and _valid_upstream_path(skill.skill_path)
        and (install_root / name).resolve() == install_root / name
        and (install_root / name / "SKILL.md").is_file()
        and not (install_root / name / "SKILL.md").is_symlink()
    )


def is_owned_file(path: Path, vendor_roots: tuple[Path, ...]) -> bool:
    """Keep source reached through a vendor symlink subject to normal checks."""
    absolute = path.absolute()
    resolved = path.resolve()
    return not any(
        absolute.is_relative_to(root) and resolved.is_relative_to(root)
        for root in vendor_roots
    )


def filter_owned_files(project_root: Path, files: list[Path]) -> list[Path]:
    """Apply the same vendor boundary to changed-file and full checks."""
    vendor_roots = installed_skill_roots(project_root)
    return [
        path
        for path in files
        if is_owned_file(
            path if path.is_absolute() else project_root / path, vendor_roots
        )
    ]
