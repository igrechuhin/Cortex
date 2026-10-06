"""Read-only discovery, link rewriting and preview fingerprints."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.security import InputValidator
from cortex.managers.types import ManagersDict
from cortex.tools.artifacts.artifact_types import get_artifact_directories
from cortex.tools.files.artifact_migration_inventory import reference_files
from cortex.tools.files.artifact_migration_links import rewrite_links
from cortex.tools.files.artifact_migration_models import (
    MigrationEdit,
    MigrationPlan,
    Relocation,
)
from cortex.tools.plans.completion_transaction_io import validate_contained_path

LEGACY_NAMES = ("reviews", "analyses", "queries")


def byte_hash(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def checked_path(root: Path, relative: str) -> Path:
    """Reject untrusted path components before resolving journal or index paths."""
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Unsafe migration path: {relative}")
    target = root / path
    validate_contained_path(target, root)
    return target


def legacy_directories(root: Path) -> tuple[Path, ...]:
    memory = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    return tuple(memory / name for name in LEGACY_NAMES)


def _tree_files(
    root: Path, anchor: Path, snapshot: dict[str, str] | None = None
) -> list[Path]:
    validate_contained_path(anchor, root)
    if not anchor.exists():
        return []
    if not anchor.is_dir():
        raise ValueError(f"Expected artifact directory: {anchor}")
    result: list[Path] = []
    for directory, directories, names in os.walk(anchor, followlinks=False):
        for name in sorted(directories + names):
            path = Path(directory) / name
            validate_contained_path(path, root)
            if path.is_dir() and snapshot is not None:
                snapshot[path.relative_to(root).as_posix()] = "directory"
            if path.is_file():
                result.append(path)
            elif not path.is_dir():
                raise ValueError(f"Not a regular migration input: {path}")
    return sorted(result)


def _validate_destination(
    root: Path, destination: Path, anchor: Path, snapshot: dict[str, str]
) -> None:
    validate_contained_path(destination, root)
    if destination.exists():
        raise ValueError(f"Artifact destination collision: {destination}")
    for parent in destination.parents:
        if parent.exists() and not parent.is_dir():
            raise ValueError(f"Artifact destination ancestor collision: {parent}")
        if parent.is_relative_to(anchor):
            snapshot[parent.relative_to(root).as_posix()] = (
                "directory" if parent.exists() else "absent_directory"
            )
        if parent == root:
            break


def _collect_moves(
    root: Path, snapshot: dict[str, str], inputs: dict[Path, bytes]
) -> dict[Path, Path]:
    moves: dict[Path, Path] = {}
    for source_dir, destination_dir in zip(
        legacy_directories(root), get_artifact_directories(root), strict=True
    ):
        for anchor in (source_dir, destination_dir):
            snapshot[anchor.relative_to(root).as_posix()] = (
                "directory" if anchor.exists() else "absent_directory"
            )
            for path in _tree_files(root, anchor, snapshot):
                inputs[path] = path.read_bytes()
        for source in _tree_files(root, source_dir, snapshot):
            for part in source.relative_to(source_dir).parts:
                _ = InputValidator.validate_file_name(part)
            destination = destination_dir / source.relative_to(source_dir)
            _validate_destination(root, destination, destination_dir, snapshot)
            moves[source] = destination
    return moves


def _collect_inputs(
    root: Path, snapshot: dict[str, str], inputs: dict[Path, bytes]
) -> None:
    for path in reference_files(root):
        _ = inputs.setdefault(path, path.read_bytes())
    cortex = get_cortex_path(root, CortexResourceType.CORTEX_DIR)
    paths = [
        get_cortex_path(root, CortexResourceType.INDEX),
        cortex / "wal" / "write_log.jsonl",
        cortex / "wal" / "artifact_relocations.jsonl",
    ]
    paths.extend(
        cortex / name for name in ("temporal.db", "temporal.db-wal", "temporal.db-shm")
    )
    for path in paths:
        validate_contained_path(path, root)
        if path.exists():
            if not path.is_file():
                raise ValueError(f"Not a regular migration input: {path}")
            inputs[path] = path.read_bytes()
        else:
            snapshot[path.relative_to(root).as_posix()] = "absent"
    for anchor in (
        get_cortex_path(root, CortexResourceType.HISTORY),
        get_cortex_path(root, CortexResourceType.WIKI) / "sources",
    ):
        for path in _tree_files(root, anchor):
            inputs[path] = path.read_bytes()


def _relocation_payloads(
    root: Path,
    source: Path,
    destination: Path,
    before: bytes,
    after: bytes,
    snapshot: dict[str, str],
) -> tuple[Relocation, list[MigrationEdit]]:
    relative = source.relative_to(root).as_posix()
    dest_rel = destination.relative_to(root).as_posix()
    snapshot[dest_rel] = "absent"
    relocation = Relocation(
        source=relative,
        destination=dest_rel,
        before_hash=byte_hash(before),
        after_hash=byte_hash(after),
    )
    return relocation, [
        MigrationEdit(path=dest_rel, before=None, after=after),
        MigrationEdit(path=relative, before=before, after=None),
    ]


def _rewrite_input(
    root: Path,
    path: Path,
    destination: Path,
    before: bytes,
    moves: dict[Path, Path],
    immutable: tuple[Path, ...],
) -> bytes:
    if path.suffix.lower() == ".md" and not any(
        path.is_relative_to(anchor) for anchor in immutable
    ):
        return rewrite_links(before, path, destination, moves, root)
    return before


def _immutable_anchors(root: Path) -> tuple[Path, Path]:
    return (
        get_cortex_path(root, CortexResourceType.HISTORY),
        get_cortex_path(root, CortexResourceType.WIKI) / "sources",
    )


def _prepare_edits(
    root: Path,
    inputs: dict[Path, bytes],
    moves: dict[Path, Path],
    snapshot: dict[str, str],
) -> tuple[list[MigrationEdit], list[Relocation], dict[Path, bytes]]:
    rewritten: dict[Path, bytes] = {}
    edits: list[MigrationEdit] = []
    relocations: list[Relocation] = []
    immutable = _immutable_anchors(root)
    for path, before in sorted(inputs.items()):
        relative = path.relative_to(root).as_posix()
        snapshot[relative] = byte_hash(before)
        destination = moves.get(path, path)
        after = _rewrite_input(root, path, destination, before, moves, immutable)
        if after != before or path in moves:
            rewritten[path] = after
        if path in moves:
            relocation, payloads = _relocation_payloads(
                root,
                path,
                destination,
                before,
                after,
                snapshot,
            )
            relocations.append(relocation)
            edits.extend(payloads)
        elif after != before:
            edits.append(MigrationEdit(path=relative, before=before, after=after))
    return edits, relocations, rewritten


def _append_index_edit(
    root: Path,
    mgrs: ManagersDict,
    inputs: dict[Path, bytes],
    moves: dict[Path, Path],
    rewritten: dict[Path, bytes],
    edits: list[MigrationEdit],
) -> None:
    from cortex.tools.files.artifact_migration_index import prepare_index

    index = get_cortex_path(root, CortexResourceType.INDEX)
    if index in inputs and moves:
        after = prepare_index(root, mgrs, inputs[index], moves, rewritten)
        if after != inputs[index]:
            edits.append(
                MigrationEdit(
                    path=index.relative_to(root).as_posix(),
                    before=inputs[index],
                    after=after,
                )
            )


def prepare_migration(root: Path, mgrs: ManagersDict) -> MigrationPlan:
    """Collect the entire preview before writing locks, receipts or report files."""
    snapshot: dict[str, str] = {}
    inputs: dict[Path, bytes] = {}
    moves = _collect_moves(root, snapshot, inputs)
    _collect_inputs(root, snapshot, inputs)
    edits, relocations, rewritten = _prepare_edits(root, inputs, moves, snapshot)
    _append_index_edit(root, mgrs, inputs, moves, rewritten, edits)
    remove = [
        path.relative_to(root).as_posix()
        for path in legacy_directories(root)
        if path.exists()
        and all(child.is_file() and child in moves for child in path.iterdir())
    ]
    digest = preview_digest(snapshot, relocations, edits, remove, str(root))
    return MigrationPlan(
        digest=digest,
        project_root=str(root),
        snapshot=snapshot,
        relocations=relocations,
        edits=edits,
        remove_directories=remove,
    )


def preview_digest(
    snapshot: dict[str, str],
    relocations: list[Relocation],
    edits: list[MigrationEdit],
    remove: list[str],
    project_root: str,
) -> str:
    """Bind receipt preimages and permitted edits to the approved preview."""
    material = {
        "project_root": project_root,
        "snapshot": snapshot,
        "relocations": [item.model_dump() for item in relocations],
        "edits": [
            {
                "path": item.path,
                "before": (
                    byte_hash(item.before) if item.before is not None else "absent"
                ),
                "after": byte_hash(item.after) if item.after is not None else "absent",
            }
            for item in edits
        ],
        "remove_directories": remove,
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return digest
