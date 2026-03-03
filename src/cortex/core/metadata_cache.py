"""Totals and usage analytics helpers for metadata index (mutating data)."""

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.models import DetailedFileMetadata, SectionMetadata

SectionLike = Sequence[SectionMetadata]


def _update_file_counters_impl(
    file_meta: DetailedFileMetadata, change_source: str
) -> None:
    """Update read/write counters in file_meta by change source."""
    if change_source == "internal":
        file_meta.write_count += 1
    else:
        file_meta.read_count += 1


def _create_new_file_metadata_impl(
    path: Path, exists: bool, change_source: str
) -> DetailedFileMetadata:
    """Build new file metadata model."""
    now = datetime.now().isoformat()
    return DetailedFileMetadata(
        path=str(path),
        exists=exists,
        size_bytes=0,
        token_count=0,
        token_model="cl100k_base",
        last_modified=now,
        content_hash="",
        sections=[],
        read_count=0,
        write_count=1 if change_source == "internal" else 0,
        current_version=0,
        version_history=[],
    )


def get_or_create_file_metadata_impl(
    files_dict: dict[str, object],
    file_name: str,
    path: Path,
    exists: bool,
    change_source: str,
) -> DetailedFileMetadata:
    """Get existing file metadata or create new. Caller may mutate returned model.

    This function is intentionally tolerant of legacy or partially invalid
    metadata entries that may exist in .cortex/index.json. When validation
    fails for an existing entry, we fall back to creating a fresh
    DetailedFileMetadata instance instead of raising, so write paths such as
    manage_file(operation="write") can repair the entry on the next update.
    """
    if file_name in files_dict:
        raw = files_dict[file_name]
        if isinstance(raw, dict):
            try:
                file_meta = DetailedFileMetadata.model_validate(
                    cast(dict[str, object], raw)
                )
            except Exception:
                # Corrupted or legacy metadata; rebuild from scratch.
                return _create_new_file_metadata_impl(path, exists, change_source)
            _update_file_counters_impl(file_meta, change_source)
            return file_meta
    return _create_new_file_metadata_impl(path, exists, change_source)


def update_file_metadata_fields_impl(
    file_meta: DetailedFileMetadata,
    exists: bool,
    size_bytes: int,
    token_count: int,
    content_hash: str,
    sections: SectionLike,
    now: str,
) -> None:
    """Update basic metadata fields on file_meta."""
    file_meta.exists = exists
    file_meta.size_bytes = size_bytes
    file_meta.token_count = token_count
    file_meta.content_hash = content_hash
    file_meta.last_modified = now
    file_meta.sections = list(sections)


def prepare_file_metadata_update_impl(
    files_dict: dict[str, object],
    file_name: str,
    path: Path,
    exists: bool,
    change_source: str,
    normalized_sections: SectionLike,
) -> tuple[DetailedFileMetadata, str]:
    """Prepare file_meta and now timestamp. Caller then updates fields and finalizes."""
    file_meta = get_or_create_file_metadata_impl(
        files_dict, file_name, path, exists, change_source
    )
    now = datetime.now().isoformat()
    return file_meta, now


def prepare_and_update_file_metadata_impl(
    files_dict: dict[str, object],
    file_name: str,
    path: Path,
    exists: bool,
    change_source: str,
    sections: SectionLike,
    size_bytes: int,
    token_count: int,
    content_hash: str,
) -> tuple[DetailedFileMetadata, str]:
    """Prepare file_meta, apply field updates, return (file_meta, now). Caller finalizes."""
    file_meta, now = prepare_file_metadata_update_impl(
        files_dict, file_name, path, exists, change_source, sections
    )
    update_file_metadata_fields_impl(
        file_meta, exists, size_bytes, token_count, content_hash, sections, now
    )
    return file_meta, now


def _try_model_dump(value: object) -> dict[str, object] | None:
    """Best-effort call to Pydantic-style model_dump()."""
    fn = getattr(value, "model_dump", None)
    if not callable(fn):
        return None
    try:
        dumped = fn(mode="json")
    except TypeError:
        return None
    return cast(dict[str, object], dumped) if isinstance(dumped, dict) else None


def convert_version_meta_to_dict_impl(
    version_meta: dict[str, object] | object,
) -> dict[str, object] | None:
    """Convert version metadata to dict (VersionMetadata or dict)."""
    from cortex.core.models import VersionMetadata

    if isinstance(version_meta, VersionMetadata):
        return version_meta.model_dump(mode="json")
    out = _try_model_dump(version_meta)
    if out is not None:
        return out
    return (
        cast(dict[str, object], version_meta)
        if isinstance(version_meta, dict)
        else None
    )


def get_files_dict_from_data(data: dict[str, object] | None) -> dict[str, object]:
    """Get files dict from index data (copy of references)."""
    out: dict[str, object] = {}
    if data is None or not isinstance(data.get("files"), dict):
        return out
    files_raw = cast(dict[str, object], data["files"])
    for k, v in files_raw.items():
        out[str(k)] = v
    return out


def finalize_file_metadata_update_impl(
    data: dict[str, object] | None,
    files_dict: dict[str, object],
    file_name: str,
    file_meta: DetailedFileMetadata,
    change_source: str,
    now: str,
) -> None:
    """Write file_meta into files_dict and data; update totals. Caller must save."""
    if change_source == "internal":
        file_meta.last_read = now
    files_dict[file_name] = file_meta.model_dump(mode="json", by_alias=True)
    if data is not None:
        data["files"] = files_dict
    recalculate_totals_impl(data)


def add_version_to_history_impl(
    data: dict[str, object] | None,
    file_name: str,
    version_meta_dict: dict[str, object],
) -> None:
    """Append version to file's version_history and set current_version. Caller must save."""
    if data is None:
        return
    files = data.get("files", {})
    if not isinstance(files, dict) or file_name not in files:
        return
    files_typed = cast(dict[str, object], files)
    file_meta_raw: object = files_typed[file_name]
    if not isinstance(file_meta_raw, dict):
        return
    file_meta = cast(dict[str, object], file_meta_raw)
    file_meta["current_version"] = version_meta_dict["version"]
    if "version_history" not in file_meta:
        file_meta["version_history"] = []
    hist_raw: object = file_meta.get("version_history")
    if isinstance(hist_raw, list):
        version_history: list[dict[str, object]] = cast(
            list[dict[str, object]], hist_raw
        )
        version_history.append(version_meta_dict)
    else:
        file_meta["version_history"] = [version_meta_dict]


def increment_read_count_impl(data: dict[str, object] | None, file_name: str) -> bool:
    """Increment read count for file and total_reads. Returns True if updated. Caller must save."""
    if data is None:
        return False
    files = data.get("files", {})
    if not isinstance(files, dict) or file_name not in files:
        return False
    files_typed = cast(dict[str, object], files)
    entry_raw: object = files_typed[file_name]
    if not isinstance(entry_raw, dict):
        return False
    entry = cast(dict[str, object], entry_raw)
    rc = entry.get("read_count", 0)
    entry["read_count"] = int(rc) + 1 if isinstance(rc, (int, float)) else 1
    entry["last_read"] = datetime.now().isoformat()
    usage_raw: object = data.get("usage_analytics", {})
    if isinstance(usage_raw, dict):
        usage = cast(dict[str, object], usage_raw)
        total_reads_val: object = usage.get("total_reads", 0)
        usage["total_reads"] = (
            int(total_reads_val) + 1 if isinstance(total_reads_val, (int, float)) else 1
        )
    return True


def remove_file_impl(data: dict[str, object] | None, file_name: str) -> bool:
    """Remove file from index data and recalc totals. Caller must save. Returns True if removed."""
    if data is None:
        return False
    files = data.get("files", {})
    if not isinstance(files, dict) or file_name not in files:
        return False
    del files[file_name]
    data["files"] = files
    recalculate_totals_impl(data)
    return True


def cleanup_stale_entries_impl(
    data: dict[str, object] | None,
    stale_files: list[str],
    dry_run: bool,
) -> int:
    """Remove stale entries from data. Caller must save. Returns count removed."""
    if not stale_files or data is None:
        return 0
    if dry_run:
        return len(stale_files)
    files = data.get("files", {})
    if not isinstance(files, dict):
        return 0
    removed = 0
    for name in stale_files:
        if name in files:
            del files[name]
            removed += 1
    recalculate_totals_impl(data)
    return removed


def recalculate_totals_impl(data: dict[str, object] | None) -> None:
    """Recalculate total_files, total_size_bytes, total_tokens in data.

    Mutates data in place. No-op if data is None.

    Args:
        data: Index data dict
    """
    if data is None:
        return
    files = data.get("files", {})
    if not isinstance(files, dict):
        return
    files_typed = cast(dict[str, object], files)
    total_files = len(files_typed)
    total_size = 0
    for f_raw in files_typed.values():
        if isinstance(f_raw, dict):
            f_dict = cast(dict[str, object], f_raw)
            size_raw: object = f_dict.get("size_bytes", 0)
            if isinstance(size_raw, (int, float)):
                total_size += int(size_raw)
    total_tokens = 0
    for f_raw in files_typed.values():
        if isinstance(f_raw, dict):
            f_dict = cast(dict[str, object], f_raw)
            token_raw: object = f_dict.get("token_count", 0)
            if isinstance(token_raw, (int, float)):
                total_tokens += int(token_raw)
    data["totals"] = {
        "total_files": total_files,
        "total_size_bytes": total_size,
        "total_tokens": total_tokens,
        "last_full_scan": datetime.now().isoformat(),
    }


def _extract_read_counts(files: dict[str, object]) -> list[dict[str, object]]:
    """Extract read counts from files data."""
    out: list[dict[str, object]] = []
    for fname, fdata in files.items():
        if isinstance(fdata, dict):
            fdata_typed = cast(dict[str, object], fdata)
            read_raw: object = fdata_typed.get("read_count", 0)
            read = int(read_raw) if isinstance(read_raw, (int, float)) else 0
            out.append({"file": str(fname), "reads": read})
    return out


def _extract_write_counts(files: dict[str, object]) -> list[dict[str, object]]:
    """Extract write counts from files data."""
    out: list[dict[str, object]] = []
    for fname, fdata in files.items():
        if isinstance(fdata, dict):
            fdata_typed = cast(dict[str, object], fdata)
            write_raw: object = fdata_typed.get("write_count", 0)
            write = int(write_raw) if isinstance(write_raw, (int, float)) else 0
            out.append({"file": str(fname), "writes": write})
    return out


def _sort_files_by_frequency(
    files_list: list[dict[str, object]], frequency_key: str
) -> list[dict[str, object]]:
    """Sort file frequency list by reads or writes (descending)."""

    def key_fn(x: dict[str, object]) -> int:
        v: object = x.get(frequency_key, 0)
        return int(v) if isinstance(v, (int, float)) else 0

    return sorted(files_list, key=key_fn, reverse=True)


def update_usage_analytics_impl(data: dict[str, object] | None) -> None:
    """Update usage_analytics (files_by_read_frequency, files_by_write_frequency).

    Mutates data in place. No-op if data is None.

    Args:
        data: Index data dict
    """
    if data is None:
        return
    files = data.get("files", {})
    if not isinstance(files, dict):
        return
    files_typed = cast(dict[str, object], files)
    by_reads = _extract_read_counts(files_typed)
    by_reads_sorted = _sort_files_by_frequency(by_reads, "reads")
    by_writes = _extract_write_counts(files_typed)
    by_writes_sorted = _sort_files_by_frequency(by_writes, "writes")
    usage = data.get("usage_analytics", {})
    if isinstance(usage, dict):
        usage["files_by_read_frequency"] = by_reads_sorted[:10]
        usage["files_by_write_frequency"] = by_writes_sorted[:10]
        data["usage_analytics"] = usage
