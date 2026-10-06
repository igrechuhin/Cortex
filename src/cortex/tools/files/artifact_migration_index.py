"""Current index metadata updates preserving artifact identity and history."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from cortex.core.metadata_cache import recalculate_totals_impl
from cortex.managers.types import ManagersDict
from cortex.tools.files.artifact_migration_prepare import byte_hash, checked_path


def _metadata_path(root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        try:
            raw = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"Index path escapes project root: {raw}") from exc
    return checked_path(root, raw)


def _rewrite_graph(value: object, paths: dict[str, str]) -> object:
    if isinstance(value, str):
        return paths.get(value, value)
    if isinstance(value, list):
        return [_rewrite_graph(item, paths) for item in cast(list[object], value)]
    if isinstance(value, dict):
        return {
            key: _rewrite_graph(item, paths)
            for key, item in cast(dict[str, object], value).items()
        }
    return value


def _update_metadata(
    root: Path,
    mgrs: ManagersDict,
    raw: object,
    moves: dict[Path, Path],
    rewritten: dict[Path, bytes],
) -> bool:
    if not isinstance(raw, dict):
        raise ValueError("Migration index metadata must be an object")
    meta = cast(dict[str, object], raw)
    raw_path = meta.get("path")
    if not isinstance(raw_path, str):
        raise ValueError("Migration index metadata has no path")
    path = _metadata_path(root, raw_path)
    changed = path in moves
    if changed:
        meta["path"] = moves[path].relative_to(root).as_posix()
    after = rewritten.get(path)
    if after is not None and meta.get("content_hash") != byte_hash(after):
        text = after.decode("utf-8")
        meta["content_hash"] = byte_hash(after)
        meta["size_bytes"] = len(after)
        meta["token_count"] = mgrs.tokens.count_tokens(text)
        meta["sections"] = [
            section.model_dump(by_alias=True)
            for section in mgrs.fs.parse_sections(text)
        ]
        changed = True
    return changed


def _update_dependency_graph(
    root: Path, data: dict[str, object], moves: dict[Path, Path]
) -> bool:
    paths = {
        source.relative_to(root).as_posix(): destination.relative_to(root).as_posix()
        for source, destination in moves.items()
    }
    paths.update(
        {str(source): str(destination) for source, destination in moves.items()}
    )
    graph = data.get("dependency_graph")
    rewritten = _rewrite_graph(graph, paths)
    if rewritten == graph:
        return False
    data["dependency_graph"] = rewritten
    return True


def _encode_index(data: dict[str, object]) -> bytes:
    totals_before = data.get("totals")
    scan = (
        cast(dict[str, object], totals_before).get("last_full_scan", "")
        if isinstance(totals_before, dict)
        else ""
    )
    recalculate_totals_impl(data)
    cast(dict[str, object], data["totals"])["last_full_scan"] = scan
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def prepare_index(
    root: Path,
    mgrs: ManagersDict,
    content: bytes,
    moves: dict[Path, Path],
    rewritten: dict[Path, bytes],
) -> bytes:
    """Change current paths/content fields, never identity keys or history entries."""
    data = cast(dict[str, object], json.loads(content))
    files = data.get("files")
    if not isinstance(files, dict):
        raise ValueError("Migration requires an index files object")
    changed = False
    for raw in cast(dict[str, object], files).values():
        changed = _update_metadata(root, mgrs, raw, moves, rewritten) or changed
    changed = _update_dependency_graph(root, data, moves) or changed
    return _encode_index(data) if changed else content
