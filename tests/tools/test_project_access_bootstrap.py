"""Safe Project Access orientation remains independent of development planning."""

import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.project_access import AccessReason, AccessState, access_summary
from cortex.tools.files.project_access.handler import handle_project_access
from cortex.tools.files.project_access.models import Action
from cortex.tools.files.project_access.policy import HASH_ENV, POLICY_ENV
from cortex.tools.plans.plan import plan
from cortex.tools.session.models import SessionStartResult
from tests.helpers.project_access_fixtures import AccessFixture, approve
from tests.helpers.tool_call_helpers import get_tool_fn
from tests.tools.session_start_fixtures import (
    build_minimal_session_managers,
    run_session_start_patched_mcp_healthy,
)

_CONFIGURATIONS = [
    ("", "", AccessReason.POLICY_PATH_MISSING),
    ("/synthetic/private-policy.json", "", AccessReason.POLICY_SHA_MISSING),
    (
        "/synthetic/private-policy.json",
        "invalid-private-digest",
        AccessReason.POLICY_SHA_INVALID,
    ),
    ("/synthetic/private-policy.json", "a" * 64, AccessReason.VALIDATION_REQUIRED),
]


@pytest.mark.parametrize("policy_path,digest,reason", _CONFIGURATIONS)
def test_configuration_summary_never_reads_or_reveals_policy(
    monkeypatch: pytest.MonkeyPatch, policy_path: str, digest: str, reason: AccessReason
) -> None:
    monkeypatch.setenv(POLICY_ENV, policy_path)
    monkeypatch.setenv(HASH_ENV, digest)
    with patch(
        "cortex.tools.files.project_access.policy.read_policy",
        side_effect=AssertionError("No policy read permitted"),
    ):
        summary = access_summary()

    assert summary.reason == reason
    assert summary.state == (
        AccessState.CONFIGURED_UNVERIFIED
        if reason == AccessReason.VALIDATION_REQUIRED
        else AccessState.DISABLED
    )
    assert tuple(
        operation.value for operation in summary.protected_operations
    ) == tuple(action.value for action in Action)
    assert summary.planning_requires_policy is False
    serialized = summary.model_dump_json()
    for private in (policy_path, digest):
        if private:
            assert private not in serialized
    assert set(json.loads(serialized)) == {
        "state",
        "reason",
        "protected_operations",
        "planning_requires_policy",
        "guidance",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("policy_path,digest,reason", _CONFIGURATIONS[:3])
async def test_unconfigured_discovery_returns_specific_safe_denial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    policy_path: str,
    digest: str,
    reason: AccessReason,
) -> None:
    monkeypatch.setenv(POLICY_ENV, policy_path)
    monkeypatch.setenv(HASH_ENV, digest)
    result = json.loads(await handle_project_access(tmp_path, '{"action":"discover"}'))

    assert result["status"] == "error"
    assert result["reason"] == reason.value
    assert result["scope"] == "project_access"
    assert result["planning_requires_policy"] is False
    assert "result" not in result
    assert "files" not in result and "datasets" not in result and "jobs" not in result
    for private in (policy_path, digest):
        if private:
            assert private not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("policy_path,digest,reason", _CONFIGURATIONS)
async def test_actual_session_and_plan_list_work_without_validated_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    policy_path: str,
    digest: str,
    reason: AccessReason,
) -> None:
    monkeypatch.setenv(POLICY_ENV, policy_path)
    monkeypatch.setenv(HASH_ENV, digest)
    managers = await build_minimal_session_managers(tmp_path)
    with patch(
        "cortex.tools.files.project_access.policy.read_policy",
        side_effect=AssertionError("Planning must not read policy"),
    ):
        session_result = await run_session_start_patched_mcp_healthy(tmp_path, managers)
        with patch(
            "cortex.tools.plans.crud.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            plan_raw = await get_tool_fn(plan)(operation="list")
            assert isinstance(plan_raw, str)
            plan_result = json.loads(plan_raw)

    assert isinstance(session_result, SessionStartResult)
    assert session_result.brief.project_access.reason == reason
    assert session_result.brief.project_access.planning_requires_policy is False
    assert plan_result["status"] == "success"
    assert plan_result["plans"] == []


def _configure_policy_failure(
    fixture: AccessFixture, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    if failure == "wrong_root":
        fixture.policy.project_root = str(fixture.root.parent)
    elif failure == "disabled":
        fixture.policy.enabled = False
    elif failure == "unsafe_file":
        fixture.policy.files = ["../private-profile.json"]
    approve(fixture, monkeypatch)
    if failure == "wrong_sha":
        monkeypatch.setenv(HASH_ENV, "0" * 64)
    elif failure == "schema":
        content = b'{"private-approval-identity":"synthetic-owner"}'
        _ = fixture.policy_path.write_bytes(content)
        monkeypatch.setenv(HASH_ENV, hashlib.sha256(content).hexdigest())
    elif failure == "missing":
        fixture.policy_path.unlink()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure,reason",
    [
        ("wrong_sha", AccessReason.POLICY_HASH_MISMATCH),
        ("wrong_root", AccessReason.POLICY_DISABLED_OR_WRONG_PROJECT),
        ("disabled", AccessReason.POLICY_DISABLED_OR_WRONG_PROJECT),
        ("schema", AccessReason.POLICY_SCHEMA_INVALID),
        ("unsafe_file", AccessReason.POLICY_PATH_UNSAFE),
        ("missing", AccessReason.POLICY_UNAVAILABLE),
    ],
)
async def test_configured_policy_still_fails_closed_without_disclosing_grants(
    access_fixture: AccessFixture,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    reason: AccessReason,
) -> None:
    _configure_policy_failure(access_fixture, monkeypatch, failure)

    summary = access_summary()
    result = json.loads(
        await handle_project_access(access_fixture.root, '{"action":"discover"}')
    )

    assert summary.state == AccessState.CONFIGURED_UNVERIFIED
    assert result["status"] == "error"
    assert result["reason"] == reason.value
    encoded = json.dumps(result)
    for private in (
        str(access_fixture.policy_path),
        str(access_fixture.root),
        "contract.md",
        "profiles",
        "synthetic-owner",
        "private-profile.json",
    ):
        assert private not in encoded
    assert "result" not in result
