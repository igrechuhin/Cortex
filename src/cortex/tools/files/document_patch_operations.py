"""Hash-guarded literal patches of existing authored Cortex Markdown."""

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from cortex.core.exceptions import FileLockTimeoutError
from cortex.core.file_system import FileSystemManager
from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.core.security import InputValidator
from cortex.memory.wal import wal_atomic_write_bytes
from cortex.tools.files.lock_guard import verify_lock_for_file_operation
from cortex.tools.plans.completion_transaction_io import validate_contained_path


class DocumentReplacement(BaseModel):
    """One unique literal replacement, never an inferred global substitution."""

    model_config = ConfigDict(extra=EXTRA_FORBID, strict=True)

    old: str = Field(min_length=1)
    new: str
    count: int = Field(ge=1, le=1)


class DocumentPatchRequest(BaseModel):
    """The caller must supply the exact raw-byte SHA-256 preimage."""

    model_config = ConfigDict(extra=EXTRA_FORBID, strict=True)

    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    replacements: list[DocumentReplacement] = Field(min_length=1)
    dry_run: StrictBool = False


def _document_target(root: Path, file_name: str) -> Path:
    parts = file_name.split("/")
    if any(part in {"", ".", ".."} for part in parts) or any(
        char == "\\" or ord(char) < 32 or ord(char) == 127 for char in file_name
    ):
        raise ValueError("Document path contains unsafe components")
    for part in parts:
        if InputValidator.validate_file_name(part) != part:
            raise ValueError("Document path must use exact, safe components")
    if (
        not (
            len(parts) >= 3
            and parts[0] == ".cortex"
            and parts[1] in {"plans", "analyses", "reviews"}
        )
        and file_name != ".cortex/memory-bank/roadmap.md"
    ):
        raise ValueError("Document target is outside the closed patch roots")
    target = root / file_name
    validate_contained_path(target, root)
    if target.suffix.lower() != ".md" or not stat.S_ISREG(target.stat().st_mode):
        raise ValueError("Document target must be an existing regular Markdown file")
    return target


def document_metadata_bytes(content: bytes) -> tuple[bytes | None, bytes | None]:
    """Keep raw frontmatter and the first document title, including DONE markers."""
    frontmatter = re.match(
        rb"\A(?:\xef\xbb\xbf)?---[ \t]*\r?\n.*?^---[ \t]*(?:\r?\n|\Z)",
        content,
        re.M | re.S,
    )
    body = content[frontmatter.end() :] if frontmatter is not None else content
    title = re.search(
        rb"^#{1}[ \t]+[^\r\n]*(?:\r?\n|\Z)|^[^\r\n]+\r?\n=+[ \t]*(?:\r?\n|\Z)",
        body,
        re.M,
    )
    return (
        frontmatter.group() if frontmatter is not None else None,
        title.group() if title is not None else None,
    )


def _replacement_spans(
    before: bytes, replacements: list[DocumentReplacement]
) -> list[tuple[int, int, bytes]]:
    spans: list[tuple[int, int, bytes]] = []
    for replacement in replacements:
        if replacement.old == replacement.new:
            raise ValueError("Replacement old and new must differ")
        old = replacement.old.encode("utf-8")
        start = before.find(old)
        if start < 0 or before.find(old, start + 1) >= 0:
            raise ValueError("Each replacement old literal must occur exactly once")
        spans.append((start, start + len(old), replacement.new.encode("utf-8")))
    spans.sort()
    if any(left[1] > right[0] for left, right in zip(spans, spans[1:])):
        raise ValueError("Duplicate or overlapping replacements are forbidden")
    return spans


def _patched_bytes(before: bytes, request: DocumentPatchRequest) -> bytes:
    _ = before.decode("utf-8")
    if hashlib.sha256(before).hexdigest() != request.expected_sha256:
        raise ValueError("Stale expected_sha256: document bytes changed; read again")
    chunks: list[bytes] = []
    cursor = 0
    for start, end, replacement in _replacement_spans(before, request.replacements):
        chunks.extend((before[cursor:start], replacement))
        cursor = end
    chunks.append(before[cursor:])
    after = b"".join(chunks)
    if after == before:
        raise ValueError("Document patch must change bytes")
    if document_metadata_bytes(before) != document_metadata_bytes(after):
        raise ValueError("Document frontmatter and title must remain unchanged")
    return after


def write_existing_document(
    root: Path, file_name: str, target: Path, before: bytes, after: bytes
) -> None:
    """Reuse byte-atomic WAL staging and the roadmap mode-preservation pattern."""
    mode = stat.S_IMODE(target.stat().st_mode)
    with TemporaryDirectory(dir=target.parent) as staging:
        staged = Path(staging) / target.name
        wal_atomic_write_bytes(Path(staging), staged, after)
        staged.chmod(mode)
        if _document_target(root, file_name) != target or target.read_bytes() != before:
            raise ValueError("Stale document bytes before atomic replacement")
        os.replace(staged, target)


def _patch_response(
    root: Path,
    file_name: str,
    before: bytes,
    after: bytes,
    request: DocumentPatchRequest,
) -> str:
    return json.dumps(
        {
            "status": "success",
            "operation": "patch_document",
            "project_root": str(root),
            "target": file_name,
            "before_sha256": hashlib.sha256(before).hexdigest(),
            "after_sha256": hashlib.sha256(after).hexdigest(),
            "replacement_counts": [1 for _ in request.replacements],
            "dry_run": request.dry_run,
            "mutation_performed": not request.dry_run,
        },
        indent=2,
    )


async def _patch_locked(
    root: Path, file_name: str, request: DocumentPatchRequest
) -> str:
    target = _document_target(root, file_name)
    before = target.read_bytes()
    after = _patched_bytes(before, request)
    if file_name == ".cortex/memory-bank/roadmap.md" and not request.dry_run:
        allowed, error = await verify_lock_for_file_operation(
            root, "roadmap.md", after.decode("utf-8"), None
        )
        if not allowed:
            raise ValueError(f"Lock verification failed: {error}")
    if not request.dry_run:
        write_existing_document(root, file_name, target, before, after)
    return _patch_response(root, file_name, before, after, request)


async def handle_document_patch(root: Path, file_name: str, content: str | None) -> str:
    """Patch only one existing document; never normalize, register or mirror it."""
    try:
        if ".." in root.parts or root.absolute() != root.resolve():
            raise ValueError("Document project root cannot traverse symlinks")
        root = root.absolute()
        request = DocumentPatchRequest.model_validate_json(content or "{}")
        target = _document_target(root, file_name)
        _ = _patched_bytes(target.read_bytes(), request)
        if request.dry_run:
            return await _patch_locked(root, file_name, request)
        lock = target.with_suffix(target.suffix + ".lock")
        validate_contained_path(lock, root)
        manager = FileSystemManager(root)
        await manager.acquire_lock(lock)
        try:
            return await _patch_locked(root, file_name, request)
        finally:
            await manager.release_lock(lock)
    except (OSError, ValueError, FileLockTimeoutError) as exc:
        return _patch_error(root, file_name, exc)


def _patch_error(root: Path, file_name: str, exc: Exception) -> str:
    return json.dumps(
        {
            "status": "error",
            "operation": "patch_document",
            "project_root": str(root.absolute()),
            "target": file_name,
            "mutation_performed": False,
            "error": str(exc),
            "error_type": type(exc).__name__,
        },
        indent=2,
    )
