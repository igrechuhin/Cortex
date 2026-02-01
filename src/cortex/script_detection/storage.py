"""Storage for captured session scripts in .cortex/script-capture/."""

import json
import uuid
from pathlib import Path

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.script_detection.models import ScriptCaptureRecord


def _capture_dir(project_root: Path) -> Path:
    """Return absolute path to script-capture directory."""
    return get_cortex_path(project_root, CortexResourceType.SCRIPT_CAPTURE)


async def ensure_capture_dir(project_root: Path) -> Path:
    """Ensure .cortex/script-capture exists; return its path."""
    directory = _capture_dir(project_root)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


async def save_capture(project_root: Path, record: ScriptCaptureRecord) -> None:
    """Write a capture record to .cortex/script-capture/{script_id}.json."""
    directory = await ensure_capture_dir(project_root)
    path = directory / f"{record.script_id}.json"
    data = record.to_storage_dict()
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    async with open_async_text_file(path, "w", "utf-8") as f:
        _ = await f.write(json_str)


async def list_captures(project_root: Path) -> list[ScriptCaptureRecord]:
    """Load all capture records from .cortex/script-capture/."""
    directory = _capture_dir(project_root)
    if not directory.exists():
        return []
    records: list[ScriptCaptureRecord] = []
    for path in sorted(directory.glob("*.json")):
        try:
            async with open_async_text_file(path, "r", "utf-8") as f:
                content = await f.read()
            data = json.loads(content)
            records.append(ScriptCaptureRecord.from_storage_dict(data))
        except (json.JSONDecodeError, Exception):
            continue
    return records


async def get_capture_by_id(
    project_root: Path, script_id: str
) -> ScriptCaptureRecord | None:
    """Load a single capture by script_id, or None if not found."""
    path = _capture_dir(project_root) / f"{script_id}.json"
    if not path.exists():
        return None
    async with open_async_text_file(path, "r", "utf-8") as f:
        content = await f.read()
    data = json.loads(content)
    return ScriptCaptureRecord.from_storage_dict(data)


def generate_script_id() -> str:
    """Generate a unique script capture ID."""
    return str(uuid.uuid4())


class ScriptCaptureStore:
    """Synchronous-style facade for script capture storage.

    All methods are async; project_root is provided at call site.
    """

    @staticmethod
    async def save(project_root: Path, record: ScriptCaptureRecord) -> None:
        """Persist a capture record."""
        await save_capture(project_root, record)

    @staticmethod
    async def list_all(project_root: Path) -> list[ScriptCaptureRecord]:
        """List all capture records."""
        return await list_captures(project_root)

    @staticmethod
    async def get_by_id(
        project_root: Path, script_id: str
    ) -> ScriptCaptureRecord | None:
        """Get one record by id."""
        return await get_capture_by_id(project_root, script_id)
