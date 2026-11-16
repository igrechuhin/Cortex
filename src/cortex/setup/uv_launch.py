"""Explicit opt-in uv storage for a newly assembled local POSIX distribution."""

import os
import shlex
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

POSIX_LAUNCH_SUPPORTED = os.name == "posix"


class UvLaunchDirectories(BaseModel):
    """Validate literal paths without creating directories or changing settings."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )
    cache_dir: Path
    tool_dir: Path

    @field_validator("cache_dir", "tool_dir", mode="before")
    @classmethod
    def literal_absolute_path(cls, value: object) -> Path:
        if not isinstance(value, (str, Path)):
            raise ValueError("uv directories must be explicit absolute paths")
        raw = str(value)
        if not raw or any(ord(char) < 32 or ord(char) == 127 for char in raw):
            raise ValueError("uv directories cannot contain control characters")
        path = Path(raw)
        if not path.is_absolute() or ".." in path.parts or path == Path(path.anchor):
            raise ValueError(
                "uv directories must be absolute non-root paths without .."
            )
        return path

    @model_validator(mode="after")
    def supported_distinct_directories(self) -> "UvLaunchDirectories":
        if not POSIX_LAUNCH_SUPPORTED:
            raise ValueError("Explicit uv plugin launch directories require POSIX")
        if self.cache_dir.is_relative_to(self.tool_dir) or self.tool_dir.is_relative_to(
            self.cache_dir
        ):
            raise ValueError(
                "uv cache and tool directories must be distinct and separate"
            )
        return self

    def environment(self) -> dict[str, str]:
        return {"UV_CACHE_DIR": str(self.cache_dir), "UV_TOOL_DIR": str(self.tool_dir)}

    def hook_prefix(self) -> str:
        # AI: Quote only literal assignments; the host's wheel-root macro must expand.
        assignments = [
            shlex.quote(f"{name}={value}") for name, value in self.environment().items()
        ]
        return "env " + " ".join(assignments) + " "


def launch_directories(
    cache_dir: Path | None, tool_dir: Path | None
) -> UvLaunchDirectories | None:
    """An omitted pair preserves legacy behavior; an incomplete pair fails closed."""
    if cache_dir is None and tool_dir is None:
        return None
    if cache_dir is None or tool_dir is None:
        raise ValueError("Provide both --uv-cache-dir and --uv-tool-dir")
    return UvLaunchDirectories(cache_dir=cache_dir, tool_dir=tool_dir)
