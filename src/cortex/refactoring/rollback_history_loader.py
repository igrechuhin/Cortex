"""
Rollback History Loader - Rollback Manager Support

Handle loading and saving rollback history from disk.
Uses Pydantic model_validate for type-safe parsing.
"""

import json
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.exceptions import FileOperationError
from cortex.core.models import JsonValue, ModelDict
from cortex.refactoring.models import RollbackRecordModel

# Type alias for rollback record data at JSON boundary
RollbackRecordData = dict[str, str | int | bool | list[str] | None]


def load_rollbacks(rollback_file: Path) -> dict[str, RollbackRecordModel]:
    """Load rollback history from disk.

    Args:
        rollback_file: Path to rollback history file

    Returns:
        Dictionary mapping rollback IDs to RollbackRecord objects
    """
    if not rollback_file.exists():
        return {}

    try:
        rollbacks_dict = _read_rollback_file(rollback_file)
        return _parse_rollbacks_dict(rollbacks_dict)
    except Exception as e:
        _handle_corrupted_history(e)
        return {}


def _read_rollback_file(rollback_file: Path) -> dict[str, RollbackRecordData]:
    """Read and extract rollbacks dictionary from file.

    Args:
        rollback_file: Path to rollback history file

    Returns:
        Dictionary of rollback data
    """
    with open(rollback_file) as f:
        data_raw: JsonValue = json.load(f)
        if not isinstance(data_raw, dict):
            return {}
        data_dict = cast(ModelDict, data_raw)
        rollbacks_raw: JsonValue = data_dict.get("rollbacks", {})
        if not isinstance(rollbacks_raw, dict):
            return {}
        # Return typed dict - JSON structure is known
        rollbacks_dict = cast(ModelDict, rollbacks_raw)
        result: dict[str, RollbackRecordData] = {}
        for key, value in rollbacks_dict.items():
            if isinstance(value, dict):
                result[str(key)] = cast(RollbackRecordData, value)
        return result


def _parse_rollbacks_dict(
    rollbacks_dict: dict[str, RollbackRecordData],
) -> dict[str, RollbackRecordModel]:
    """Parse rollbacks dictionary into RollbackRecordModel objects.

    Args:
        rollbacks_dict: Dictionary of rollback data

    Returns:
        Dictionary mapping rollback IDs to RollbackRecordModel objects
    """
    rollbacks: dict[str, RollbackRecordModel] = {}
    for rollback_id, rollback_data in rollbacks_dict.items():
        try:
            # Add rollback_id to data if not present for validation
            if "rollback_id" not in rollback_data:
                rollback_data["rollback_id"] = rollback_id
            rollbacks[str(rollback_id)] = RollbackRecordModel.model_validate(
                rollback_data
            )
        except ValidationError:
            # Skip invalid records
            continue
    return rollbacks


def _handle_corrupted_history(error: Exception) -> None:
    """Handle corrupted rollback history by logging warning.

    Args:
        error: The exception that occurred during loading
    """
    from cortex.core.logging_config import logger

    logger.warning(f"Rollback history corrupted, starting fresh: {error}")


async def save_rollbacks(
    rollback_file: Path, rollbacks: dict[str, RollbackRecordModel]
) -> None:
    """Save rollback history to disk.

    Args:
        rollback_file: Path to rollback history file
        rollbacks: Dictionary of rollback records

    Raises:
        FileOperationError: If save fails
    """
    try:
        from datetime import datetime

        data = {
            "last_updated": datetime.now().isoformat(),
            "rollbacks": {
                rollback_id: rollback.model_dump(mode="json")
                for rollback_id, rollback in rollbacks.items()
            },
        }
        async with open_async_text_file(rollback_file, "w", "utf-8") as f:
            _ = await f.write(json.dumps(data, indent=2))
    except Exception as e:
        raise FileOperationError(f"Failed to save rollback history: {e}") from e
