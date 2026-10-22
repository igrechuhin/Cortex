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
from cortex.tools.files.guarded_mutation_evidence import GuardedMutationEvidence
from cortex.tools.files.guarded_operation_outcome import GuardedOperationOutcome
from cortex.tools.files.guarded_operation_refusal import (
    GuardedOperationRefusal,
    validate_guarded_path,
)
from cortex.tools.files.lock_guard import verify_lock_for_file_operation

_ENTRY_TARGETS = frozenset(
    {".cortex/memory-bank/activeContext.md", ".cortex/memory-bank/progress.md"}
)
_MEMORY_BANK_TARGETS = _ENTRY_TARGETS | {".cortex/memory-bank/roadmap.md"}
_ENTRY_PREFIX = re.compile(r"^[ \t]*(?:(?:[-+*]|\d+[.)])[ \t]+(?:\[[ xX]\][ \t]+)?)*")
_LIFECYCLE_MARKERS = re.compile(
    r"\b(?:PENDING|IN_PROGRESS|BLOCKED|DONE|READY|COMPLETE(?:D)?|PARTIAL|"
    + r"CANCEL(?:L)?ED|ARCHIVED|REJECTED|HELD|RESOLVED|WONTFIX|NOT_JUSTIFIED|"
    + r"ACTIVE|operator|agent)\b",
    re.I,
)


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


def _document_path_parts(file_name: str) -> list[str]:
    parts = file_name.split("/")
    if any(part in {"", ".", ".."} for part in parts) or any(
        char == "\\" or ord(char) < 32 or ord(char) == 127 for char in file_name
    ):
        raise GuardedOperationRefusal("Document path contains unsafe components")
    for part in parts:
        try:
            canonical = InputValidator.validate_file_name(part)
        except ValueError as exc:
            raise GuardedOperationRefusal(str(exc)) from exc
        if canonical != part:
            raise GuardedOperationRefusal(
                "Document path must use exact, safe components"
            )
    return parts


def _document_target(root: Path, file_name: str) -> Path:
    parts = _document_path_parts(file_name)
    if (
        not (
            len(parts) >= 3
            and parts[0] == ".cortex"
            and parts[1] in {"plans", "analyses", "reviews"}
        )
        and file_name not in _MEMORY_BANK_TARGETS
    ):
        raise GuardedOperationRefusal(
            "Document target is outside the closed patch roots"
        )
    target = root / file_name
    validate_guarded_path(target, root)
    if target.suffix.lower() != ".md" or not stat.S_ISREG(target.stat().st_mode):
        raise GuardedOperationRefusal(
            "Document target must be an existing regular Markdown file"
        )
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
            raise GuardedOperationRefusal("Replacement old and new must differ")
        old = replacement.old.encode("utf-8")
        start = before.find(old)
        if start < 0 or before.find(old, start + 1) >= 0:
            raise GuardedOperationRefusal(
                "Each replacement old literal must occur exactly once"
            )
        spans.append((start, start + len(old), replacement.new.encode("utf-8")))
    spans.sort()
    if any(left[1] > right[0] for left, right in zip(spans, spans[1:])):
        raise GuardedOperationRefusal(
            "Duplicate or overlapping replacements are forbidden"
        )
    return spans


def _patched_bytes(
    before: bytes, request: DocumentPatchRequest, file_name: str
) -> bytes:
    _ = before.decode("utf-8")
    if hashlib.sha256(before).hexdigest() != request.expected_sha256:
        raise GuardedOperationRefusal(
            "Stale expected_sha256: document bytes changed; read again",
            GuardedOperationOutcome.STALE_BASE,
        )
    chunks: list[bytes] = []
    cursor = 0
    for start, end, replacement in _replacement_spans(before, request.replacements):
        chunks.extend((before[cursor:start], replacement))
        cursor = end
    chunks.append(before[cursor:])
    after = b"".join(chunks)
    if after == before:
        raise GuardedOperationRefusal("Document patch must change bytes")
    if document_metadata_bytes(before) != document_metadata_bytes(after):
        raise GuardedOperationRefusal(
            "Document frontmatter and title must remain unchanged"
        )
    if file_name in _ENTRY_TARGETS:
        _validate_entry_patch(before, after, request)
    return after


def _entry_markers(line: str) -> tuple[str, ...]:
    """Freeze entry identity, list/check-box syntax, comments and lifecycle words."""
    prefix = _ENTRY_PREFIX.match(line)
    label = re.search(r"\*\*.+?\*\*", line)
    return (
        prefix.group() if prefix is not None else "",
        label.group() if label is not None else "",
        *(match.group() for match in re.finditer(r"<!--.*?-->", line)),
        *(match.group() for match in _LIFECYCLE_MARKERS.finditer(line)),
        *(
            match.group()
            for match in re.finditer(
                r"\b(?:status|execution|lifecycle)\s*[:=]\s*\S+", line, re.I
            )
        ),
    )


def _entry_structure(line: str) -> bool:
    """Only ordinary entry prose is repairable, not Markdown outline/blocks."""
    return (
        not line.strip()
        or line.startswith(("    ", "\t"))
        or re.fullmatch(r"\s*(?:[-*_]\s*){3,}", line) is not None
        or re.match(
            r"^(?: {4}|\t)|^\s*(?:#{1,6}(?:\s|$)|[=-]+\s*$|(?:[-*_]\s*){3,}$|"
            + r"\x60{3,}|~{3,}|>|<|\||\[.*?\]:)",
            _ENTRY_PREFIX.sub("", line),
        )
        is not None
    )


def _entry_fence(line: str, fence: str | None) -> str | None:
    marker = re.match(r"^(\x60{3,}|~{3,})(.*)$", _ENTRY_PREFIX.sub("", line))
    if marker is None:
        return fence
    delimiter, suffix = marker.groups()
    if fence is None:
        return delimiter
    if delimiter[0] == fence[0] and len(delimiter) >= len(fence) and not suffix.strip():
        return None
    return fence


def _validate_entry_literals(request: DocumentPatchRequest) -> None:
    for replacement in request.replacements:
        if not replacement.new.strip() or any(
            char in "\r\n\v\f\x85\u2028\u2029" or ord(char) < 32
            for char in replacement.old + replacement.new
        ):
            raise GuardedOperationRefusal(
                "Entry repairs require nonempty single-line literals"
            )


def _validate_entry_identity(
    old: str, new: str, old_lines: list[str], new_lines: list[str]
) -> None:
    if _entry_markers(old) != _entry_markers(new):
        raise GuardedOperationRefusal(
            "Entry labels, list syntax and status/lifecycle markers must remain unchanged"
        )
    if new in old_lines or new_lines.count(new) > 1:
        raise GuardedOperationRefusal(
            "Entry repairs cannot duplicate or reorder existing lines"
        )


def _validate_entry_patch(
    before: bytes, after: bytes, request: DocumentPatchRequest
) -> None:
    _validate_entry_literals(request)
    old_lines, new_lines = (
        before.decode("utf-8").splitlines(),
        after.decode("utf-8").splitlines(),
    )
    fence: str | None = None
    for index, (old, new) in enumerate(zip(old_lines, new_lines, strict=True)):
        fence = _entry_fence(old, fence)
        if old == new:
            continue
        setext = index + 1 < len(old_lines) and re.fullmatch(
            r"\s*[=-]+\s*", old_lines[index + 1]
        )
        if (
            fence is not None
            or setext
            or _entry_structure(old)
            or _entry_structure(new)
        ):
            raise GuardedOperationRefusal(
                "Entry repairs cannot change headings or Markdown blocks"
            )
        _validate_entry_identity(old, new, old_lines, new_lines)


def write_existing_document(
    root: Path,
    file_name: str,
    target: Path,
    before: bytes,
    after: bytes,
    evidence: GuardedMutationEvidence,
) -> None:
    """Reuse byte-atomic WAL staging and the roadmap mode-preservation pattern."""
    mode = stat.S_IMODE(target.stat().st_mode)
    with TemporaryDirectory(dir=target.parent) as staging:
        staged = Path(staging) / target.name
        wal_atomic_write_bytes(Path(staging), staged, after)
        staged.chmod(mode)
        revalidated = _document_target(root, file_name)
        current = evidence.observe(root, revalidated)
        if revalidated != target or current != before:
            raise GuardedOperationRefusal(
                "Stale document bytes before atomic replacement",
                GuardedOperationOutcome.STALE_BASE,
            )
        os.replace(staged, target)
        evidence.replaced(after)


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
    root: Path,
    file_name: str,
    request: DocumentPatchRequest,
    evidence: GuardedMutationEvidence,
) -> str:
    target = _document_target(root, file_name)
    before = evidence.observe(root, target)
    after = _patched_bytes(before, request, file_name)
    if file_name == ".cortex/memory-bank/roadmap.md":
        allowed, error = await verify_lock_for_file_operation(
            root, "roadmap.md", after.decode("utf-8"), None
        )
        if not allowed:
            raise GuardedOperationRefusal(f"Lock verification failed: {error}")
    if not request.dry_run:
        write_existing_document(root, file_name, target, before, after, evidence)
    return _patch_response(root, file_name, before, after, request)


async def handle_document_patch(root: Path, file_name: str, content: str | None) -> str:
    """Patch only one existing document; never normalize, register or mirror it."""
    evidence = GuardedMutationEvidence()
    try:
        if ".." in root.parts or root.absolute() != root.resolve():
            raise GuardedOperationRefusal(
                "Document project root cannot traverse symlinks"
            )
        root = root.absolute()
        request = DocumentPatchRequest.model_validate_json(content or "{}")
        target = _document_target(root, file_name)
        _ = _patched_bytes(evidence.observe(root, target), request, file_name)
        lock = target.with_suffix(target.suffix + ".lock")
        validate_guarded_path(lock, root)
        if request.dry_run:
            return await _patch_locked(root, file_name, request, evidence)
        manager = FileSystemManager(root)
        await manager.acquire_lock(lock)
        try:
            return await _patch_locked(root, file_name, request, evidence)
        finally:
            await manager.release_lock(lock)
    except (OSError, ValueError, FileLockTimeoutError) as exc:
        return _patch_error(root, evidence, exc)


def _patch_error(root: Path, evidence: GuardedMutationEvidence, exc: Exception) -> str:
    return json.dumps(
        {
            **evidence.error_fields(exc),
            "operation": "patch_document",
            "project_root": str(root.absolute()),
        },
        indent=2,
    )
