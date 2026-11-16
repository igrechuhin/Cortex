"""One explicit manage_file operation; existing file permissions are unchanged."""

import asyncio
import json
import sqlite3
from pathlib import Path

from pydantic import ValidationError

from cortex.tools.files.project_access.jobs import read_output, start, status
from cortex.tools.files.project_access.models import (
    Action,
    ApprovedAccess,
    Request,
    Scope,
)
from cortex.tools.files.project_access.paths import (
    MAX_RESPONSE_BYTES,
    read_text,
    screen_text,
)
from cortex.tools.files.project_access.policy import load_access
from cortex.tools.files.project_access.sqlite_read import query


def dispatch(root: Path, content: str | None) -> dict[str, object]:
    """Policy grants nothing until independently approved by the operator."""
    access = load_access(root)
    if content is None or len(content.encode()) > 16384:
        raise ValueError("project_access content must be a bounded JSON request")
    request = Request.model_validate_json(content)
    if request.scope == Scope.DATA:
        return dispatch_data(access, request)
    if request.action == Action.DISCOVER:
        return {
            "files": access.policy.files,
            "datasets": {k: v.columns for k, v in access.policy.datasets.items()},
            "jobs": {k: v.parameters for k, v in access.policy.jobs.items()},
        }
    if request.action == Action.READ:
        if request.path not in access.policy.files:
            raise ValueError("Exact file path is not approved")
        return read_text(access.root, request.path, request.offset, request.length)
    if request.action == Action.QUERY:
        return query(access, request)
    if request.action == Action.START:
        return start(access, request)
    if request.action == Action.STATUS:
        return status(access, request)
    return read_output(access, request)


def dispatch_data(access: ApprovedAccess, request: Request) -> dict[str, object]:
    """Legacy calculations cannot select or inherit the new data-root grant."""
    grant = access.policy.data_root
    if access.data_root is None or grant is None:
        raise ValueError(
            "Data root access disabled: separate operator approval required"
        )
    if request.action == Action.DISCOVER:
        return {
            "files": grant.files,
            "datasets": {k: v.columns for k, v in grant.datasets.items()},
            "output_bases": list(grant.output_bases),
        }
    if request.action == Action.READ and request.path in grant.files:
        return read_text(access.data_root, request.path, request.offset, request.length)
    if request.action == Action.QUERY:
        return query(access, request)
    raise ValueError(
        "Data scope permits only exact approved reads and structured queries"
    )


async def handle_project_access(root: Path, content: str | None) -> str:
    """Keep blocking file/SQLite work off the MCP loop and redact error payloads."""
    try:
        result = await asyncio.to_thread(dispatch, root, content)
        encoded = screen_text(json.dumps({"status": "success", "result": result}))
        if len(encoded.encode()) > MAX_RESPONSE_BYTES:
            raise ValueError("Project access response exceeds the result limit")
    except ValidationError:
        return json.dumps(
            {"status": "error", "error": "Invalid project-access policy/request schema"}
        )
    except (OSError, UnicodeError, sqlite3.Error, TypeError):
        return json.dumps(
            {
                "status": "error",
                "error": "Project access refused: input unavailable or unsafe",
            }
        )
    except ValueError as exc:
        return json.dumps({"status": "error", "error": str(exc)})
    return encoded
