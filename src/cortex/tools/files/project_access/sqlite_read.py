"""Bounded SELECT-only queries over stable, approved SQLite snapshots."""

import hashlib
import json
import math
import os
import re
import sqlite3
import time

from cortex.tools.files.project_access.models import ApprovedAccess, Dataset, Request
from cortex.tools.files.project_access.paths import (
    MAX_RESPONSE_BYTES,
    directory,
    read_bytes,
    relative_parts,
    screen_text,
)


def identifier(value: str) -> str:
    """Only simple configured identifiers enter SQL; values stay bound."""
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", value):
        raise ValueError("Invalid approved database identifier")
    return f'"{value}"'


def snapshot(access: ApprovedAccess, dataset: Dataset) -> bytes:
    """Never silently omit committed WAL rows or load a hot rollback journal."""
    parts = relative_parts(dataset.path)
    with directory(access.root, parts[:-1]) as parent:
        ensure_no_sidecars(parent, parts[-1])
        data = read_bytes(access.root, dataset.path, dataset.max_bytes)
        # AI: Recheck sidecars after copying; active databases require their existing exporter.
        ensure_no_sidecars(parent, parts[-1])
    return data


def ensure_no_sidecars(parent: int, name: str) -> None:
    """Use descriptor-relative checks on both macOS and Linux."""
    for suffix in ("-wal", "-journal"):
        try:
            _ = os.stat(name + suffix, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            continue
        raise ValueError(
            "SQLite source must be a quiescent snapshot without WAL/journal"
        )


def select_sql(
    dataset: Dataset, request: Request
) -> tuple[str, list[str | int | float | None]]:
    """Build one bounded SELECT from a closed table/column policy."""
    if request.offset > 10000 or not set(request.filters).issubset(dataset.columns):
        raise ValueError("Unapproved filter or query offset")
    values = list(request.filters.values())
    if any(
        isinstance(v, str)
        and len(v) > 512
        or isinstance(v, float)
        and not math.isfinite(v)
        or isinstance(v, int)
        and not -(2**63) <= v < 2**63
        for v in values
    ):
        raise ValueError("Filter value exceeds bounds")
    columns = ", ".join(identifier(c) for c in dataset.columns)
    where = " AND ".join(f"{identifier(c)} IS ?" for c in request.filters)
    sql = f"SELECT {columns} FROM {identifier(dataset.table)}"
    if where:
        sql += " WHERE " + where
    sql += f" ORDER BY {columns} LIMIT ? OFFSET ?"
    return sql, values + [request.limit, request.offset]


def configure_readonly(connection: sqlite3.Connection, dataset: Dataset) -> None:
    """Disallow views, virtual tables, functions, writes and attachment."""
    row = connection.execute(
        "SELECT type, sql FROM sqlite_schema WHERE name = ?", (dataset.table,)
    ).fetchone()
    if row is None or row[0] != "table" or "VIRTUAL" in str(row[1]).upper():
        raise ValueError("Only an approved ordinary base table can be queried")
    _ = connection.execute("PRAGMA query_only = ON")
    _ = connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_RESPONSE_BYTES)
    _ = connection.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True)
    deadline = time.monotonic() + 2
    connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)

    def authorize(
        action: int,
        table: str | None,
        column: str | None,
        _database: str | None,
        _trigger: str | None,
    ) -> int:
        if action == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if (
            action == sqlite3.SQLITE_READ
            and table == dataset.table
            and column in dataset.columns
        ):
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    connection.set_authorizer(authorize)


def query(access: ApprovedAccess, request: Request) -> dict[str, object]:
    """Read full approved scalar values, rejecting oversize or sensitive results."""
    dataset = access.policy.datasets.get(request.dataset)
    if dataset is None:
        raise ValueError("Dataset is not approved")
    sql, values = select_sql(dataset, request)
    data = snapshot(access, dataset)
    with sqlite3.connect(":memory:") as connection:
        connection.deserialize(data)
        configure_readonly(connection, dataset)
        rows = connection.execute(sql, values).fetchall()
    result: dict[str, object] = {
        "columns": dataset.columns,
        "rows": rows,
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "offset": request.offset,
        "limit": request.limit,
        "returned": len(rows),
    }
    encoded = screen_text(json.dumps(result, allow_nan=False))
    if len(encoded.encode()) > MAX_RESPONSE_BYTES:
        raise ValueError("Query result too large; narrow filters or lower limit")
    return result
