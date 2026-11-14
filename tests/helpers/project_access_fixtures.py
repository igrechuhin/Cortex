"""Shared temporary fixtures and typed responses for project-access tests."""

import asyncio
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from cortex.tools.files.manage_file_helpers import execute_file_operation
from cortex.tools.files.operation_helpers import (
    FileOperation,
)
from cortex.tools.files.project_access.models import Policy, Terminal
from cortex.tools.files.project_access.policy import HASH_ENV, POLICY_ENV

_SAFE_SCRIPT = """import os, pathlib, sys
from dataclasses import dataclass
@dataclass
class Profile:
    figi: str
assert sys.modules['__main__'].Profile is Profile
assert __package__ is None and __spec__ is None
assert pathlib.Path(__file__).name == 'prepare.py'
target = pathlib.Path(sys.argv[1]) / 'profile.txt'
target.write_text('Original profile: ' + Profile(sys.argv[2]).figi, encoding='utf-8')
(target.parent / 'environment.txt').write_text(str(os.getenv('FIXTURE_CREDENTIAL', 'absent')))
"""


class AccessFixture(BaseModel):
    root: Path
    policy_path: Path
    policy: Policy


class Payload(BaseModel):
    text: str = ""
    next_offset: int | None = None
    files: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list[list[str]])
    source_sha256: str = ""
    state: str | Terminal = ""
    task: str = ""
    duplicate: bool | None = None


class Response(BaseModel):
    status: str
    error: str = ""
    result: Payload = Field(default_factory=Payload)


def terminal_outcome(payload: Payload) -> str:
    assert isinstance(payload.state, Terminal)
    return payload.state.outcome.value


def approve(fixture: AccessFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate operator pinning, only for a temporary test project."""
    content = fixture.policy.model_dump_json().encode()
    _ = fixture.policy_path.write_bytes(content)
    monkeypatch.setenv(POLICY_ENV, str(fixture.policy_path))
    monkeypatch.setenv(HASH_ENV, hashlib.sha256(content).hexdigest())


def fixture_policy(root: Path) -> Policy:
    """Closed policy for fixture sources and a harmless existing script."""
    return Policy.model_validate_json(
        json.dumps(
            {
                "enabled": True,
                "project_root": str(root),
                "output_directory": "artifacts",
                "files": ["contract.md"],
                "datasets": {
                    "profiles": {
                        "path": "profiles.sqlite",
                        "table": "profiles",
                        "columns": ["figi", "profile"],
                    }
                },
                "jobs": {
                    "prepare": {
                        "interpreter": sys.executable,
                        "script": "prepare.py",
                        "sha256": hashlib.sha256(_SAFE_SCRIPT.encode()).hexdigest(),
                        "arguments": ["{output_directory}", "{figi}"],
                        "parameters": {"figi": ["FIGI1", "FIGI2"]},
                        "timeout": 10,
                    }
                },
            }
        )
    )


@pytest.fixture
def access_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AccessFixture:
    root = (tmp_path / "project").resolve()
    root.mkdir()
    (root / "artifacts").mkdir()
    _ = (root / "contract.md").write_text("Full original contract: αβγ\n")
    _ = (root / "prepare.py").write_text(_SAFE_SCRIPT)
    with sqlite3.connect(root / "profiles.sqlite") as db:
        _ = db.execute(
            "CREATE TABLE profiles (figi TEXT PRIMARY KEY, profile TEXT, internal TEXT)"
        )
        _ = db.execute(
            "INSERT INTO profiles VALUES (?, ?, ?)",
            ("FIGI1", "Full original profile", "excluded"),
        )
    policy = fixture_policy(root)
    fixture = AccessFixture(
        root=root, policy_path=tmp_path.resolve() / "approval.json", policy=policy
    )
    approve(fixture, monkeypatch)
    return fixture


async def call(fixture: AccessFixture, **kwargs: object) -> Response:
    """Exercise the existing manage_file dispatch with real policy validation."""
    result = await execute_file_operation(
        fixture.root,
        "project_access",
        FileOperation.PROJECT_ACCESS,
        json.dumps(kwargs),
        False,
        None,
        None,
    )
    return Response.model_validate_json(result)


async def wait_terminal(fixture: AccessFixture, figi: str = "FIGI1") -> Payload:
    for _ in range(200):
        result = await call(
            fixture, action="status", job="prepare", parameters={"figi": figi}
        )
        if isinstance(result.result.state, Terminal):
            return result.result
        await asyncio.sleep(0.05)
    raise AssertionError("Fixture job did not publish terminal status")
