"""Descriptor-relative access rejects traversal, symlinks and special files."""

# cspell:words AKIA pousr

import os
import re
import stat
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

MAX_TEXT_BYTES = 16777216
MAX_RESPONSE_BYTES = 131072
_SENSITIVE = re.compile(
    r"(^\.|secret|credential|password|token|private|id_rsa|id_ed25519)|"
    + r"\.(pem|key|p12|pfx|keystore)$",
    re.IGNORECASE,
)
_SECRET_CONTENT = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    + r"\b(?:api[_-]?key|password|secret|access[_-]?token)['\"]?\s*[=:]\s*\S+|"
    + r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|\bgh[pousr]_[A-Za-z0-9]{20,}|"
    + r"\bsk-[A-Za-z0-9_-]{20,}",
    re.IGNORECASE,
)


def relative_parts(value: str) -> tuple[str, ...]:
    """Accept only canonical, visible, nonsensitive project-relative paths."""
    parts = value.split("/")
    if (
        not value
        or len(value) > 512
        or "\\" in value
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
        or any(p in {"", ".", ".."} or _SENSITIVE.search(p) for p in parts)
    ):
        raise ValueError("Path is not an approved project-relative path")
    return tuple(parts)


@contextmanager
def directory(root: Path, parts: tuple[str, ...] = ()) -> Iterator[int]:
    """Walk with openat and O_NOFOLLOW, retaining the directory inode."""
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts:
            next_fd = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
            )
            os.close(fd)
            fd = next_fd
        yield fd
    finally:
        os.close(fd)


def read_bytes(root: Path, relative: str, maximum: int) -> bytes:
    """Bounded regular-file read, rejecting hard links and changed inputs."""
    parts = relative_parts(relative)
    with directory(root, parts[:-1]) as parent:
        fd = os.open(
            parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
        )
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_size > maximum
            ):
                raise ValueError("Expected a bounded, unlinked regular file")
            content = stream.read(maximum + 1)
            after = os.fstat(stream.fileno())
    if len(content) > maximum or (
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError("Input changed during read or exceeded size limit")
    return content


def screen_text(text: str) -> str:
    """Fail closed on known credential material; never return matched text."""
    if "\x00" in text or _SECRET_CONTENT.search(text):
        raise ValueError("Content refused by secret/binary screening")
    return text


def read_text(root: Path, path: str, offset: int, length: int) -> dict[str, object]:
    """Read exact text in character pages without silently clipping originals."""
    text = screen_text(read_bytes(root, path, MAX_TEXT_BYTES).decode("utf-8"))
    end = min(offset + length, len(text))
    return {
        "text": text[offset:end],
        "offset": offset,
        "next_offset": end if end < len(text) else None,
        "total_characters": len(text),
    }


def create_directory(root: Path, parent: str, name: str) -> bool:
    """Exclusive reservation shared across processes; never follow an alias."""
    with directory(root, relative_parts(parent)) as fd:
        try:
            os.mkdir(name, mode=0o700, dir_fd=fd)
        except FileExistsError:
            return False
    return True


def write_new(root: Path, path: str, content: bytes) -> None:
    """Publish complete bytes atomically and exclusively inside a reservation."""
    parts = relative_parts(path)
    with directory(root, parts[:-1]) as parent:
        temporary = "pending-" + uuid.uuid4().hex
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent,
        )
        try:
            with os.fdopen(fd, "wb") as stream:
                _ = stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(
                temporary,
                parts[-1],
                src_dir_fd=parent,
                dst_dir_fd=parent,
                follow_symlinks=False,
            )
        finally:
            os.unlink(temporary, dir_fd=parent)


def remove_directory(root: Path, parent: str, name: str) -> None:
    """Release only an empty lock directory through a retained parent descriptor."""
    with directory(root, relative_parts(parent)) as fd:
        os.rmdir(name, dir_fd=fd)
