"""Recovery of interrupted quality-worker leases after confirmed teardown."""

# cspell:words pgid

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.tools.execution.pre_commit_ownership import current_owner
from cortex.tools.execution.pre_commit_workspace import (
    LeaseState,
    WorkspaceBusy,
    WorkspaceLease,
    workspace_lease,
)
from cortex.tools.execution.session_paths import session_dir
from tests.helpers.quality_lease_fixtures import (
    Control,
    lifetime_alive,
    request_release,
    start_stub,
    wait_exit,
)
from tests.helpers.quality_workspace_fixtures import (
    assert_foreign_busy,
    assert_next_foreign_launch,
    prepare_workspace,
    start_foreign,
    wait_for_fixture_json,
)
from tests.helpers.quality_workspace_fixtures import (
    cooperative_lifetimes as cooperative_lifetimes,
)


@pytest.mark.parametrize("with_descendant", [False, True])
def test_bound_completion_receipt_recovers_interrupted_lease(
    tmp_path: Path, with_descendant: bool
) -> None:
    prepare_workspace(tmp_path, "receipt_descendant" if with_descendant else "receipt")
    first = start_stub(tmp_path)
    _ = wait_for_fixture_json(tmp_path / "worker.json")
    if with_descendant:
        _ = wait_for_fixture_json(tmp_path / "descendant.json")
        wait_exit(tmp_path, "worker", require_group_gone=False)
        assert lifetime_alive(tmp_path, "descendant")
        assert_foreign_busy(start_foreign(tmp_path))
        _ = (tmp_path / Control.RELEASE.value).write_text("release descendant")
        wait_exit(tmp_path, "descendant")
    else:
        _ = (tmp_path / Control.EXIT_SUPERVISOR.value).write_text("interrupt worker")
    wait_exit(tmp_path, "worker")

    state_dir = session_dir(tmp_path)
    lease_file = state_dir / "quality-worker-lease.json"
    receipt_file = state_dir / f"pre_commit_result_{first['job_id']}.json"
    lease = WorkspaceLease.model_validate_json(lease_file.read_bytes())
    assert lease.state is LeaseState.RUNNING
    assert json.loads(receipt_file.read_bytes())["workspace_completion_attempt"] == (
        lease.attempt_id
    )
    assert_next_foreign_launch(tmp_path)
    assert receipt_file.exists()


def test_uncertain_timeout_receipt_cannot_release_escaped_descendant(
    tmp_path: Path,
) -> None:
    prepare_workspace(tmp_path, "timeout_escaped_descendant")
    first = start_stub(tmp_path)
    _ = wait_for_fixture_json(tmp_path / "worker.json")
    _ = wait_for_fixture_json(tmp_path / "descendant.json")
    _ = (tmp_path / Control.EXIT_SUPERVISOR.value).write_text("finish timed-out checks")
    wait_exit(tmp_path, "worker")
    receipt_file = session_dir(tmp_path) / f"pre_commit_result_{first['job_id']}.json"
    receipt = json.loads(receipt_file.read_bytes())

    assert receipt["status"] == "completed"
    assert receipt["result"]["results"]["tests"]["execution_uncertain"] is True
    assert "workspace_completion_attempt" not in receipt
    assert lifetime_alive(tmp_path, "descendant")
    assert_foreign_busy(start_foreign(tmp_path))

    _ = (tmp_path / Control.RELEASE.value).write_text("release descendant")
    wait_exit(tmp_path, "descendant")
    assert_foreign_busy(start_foreign(tmp_path))
    assert len((tmp_path / "executions.txt").read_text().splitlines()) == 1


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires Darwin process lineage")
def test_swift_timeout_allows_next_foreign_gate(tmp_path: Path) -> None:
    prepare_workspace(tmp_path, "swift_timeout")
    first = start_stub(tmp_path)
    _ = wait_for_fixture_json(tmp_path / "descendant.json")
    wait_exit(tmp_path, "worker")
    attempt, uncertain = _swift_timeout_receipt(tmp_path, first["job_id"])
    lease_path = session_dir(tmp_path) / "quality-worker-lease.json"
    lease = WorkspaceLease.model_validate_json(lease_path.read_bytes())

    assert lease.state is LeaseState.TERMINAL
    assert attempt == lease.attempt_id
    assert uncertain is False
    assert not lifetime_alive(tmp_path, "descendant")
    assert_next_foreign_launch(tmp_path)


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires Darwin process lineage")
@pytest.mark.parametrize("case", ["live", "escaped", "unavailable"])
def test_unverified_swift_timeout_blocks_next_gate(tmp_path: Path, case: str) -> None:
    prepare_workspace(tmp_path, f"swift_timeout_{case}")
    first = start_stub(tmp_path)
    _ = wait_for_fixture_json(tmp_path / "descendant.json")
    wait_exit(tmp_path, "worker", require_group_gone=case != "live")
    attempt, uncertain = _swift_timeout_receipt(tmp_path, first["job_id"])

    assert attempt is None
    assert uncertain is True
    assert lifetime_alive(tmp_path, "descendant") is (case != "unavailable")
    assert_foreign_busy(start_foreign(tmp_path))
    request_release(tmp_path)
    wait_exit(tmp_path, "descendant")
    assert_foreign_busy(start_foreign(tmp_path))


def _swift_timeout_receipt(root: Path, job_id: object) -> tuple[str | None, bool]:
    result_file = session_dir(root) / f"pre_commit_result_{job_id}.json"
    receipt = json.loads(result_file.read_bytes())
    assert receipt["status"] == "completed"
    tests = receipt["result"]["results"]["tests"]
    assert tests["success"] is False
    assert "Test execution exceeded timeout" in tests["errors"]
    attempt = receipt.get("workspace_completion_attempt")
    assert ("workspace_completion_attempt" in receipt) == (attempt is not None)
    return attempt, tests["execution_uncertain"]


@pytest.mark.parametrize(
    "case", ["reused_pid", "legacy", "missing_receipt", "wrong_owner", "probe_denied"]
)
def test_unconfirmed_lease_cannot_be_replaced(tmp_path: Path, case: str) -> None:
    request = "a" * 12
    owner = current_owner()
    lease = WorkspaceLease(
        version=1 if case == "legacy" else 2,
        owner=owner,
        request_id=request,
        attempt_id=None if case == "legacy" else "1" * 32,
        state=LeaseState.RUNNING,
        pgid=1234,
    )
    state_dir = session_dir(tmp_path)
    lease_path = state_dir / "quality-worker-lease.json"
    original = lease.model_dump_json()
    _ = lease_path.write_text(original)
    if case != "missing_receipt":
        _write_unconfirmed_receipt(state_dir, lease, case)

    error = PermissionError() if case == "probe_denied" else ProcessLookupError()
    with patch(
        "cortex.tools.execution.pre_commit_workspace.os.killpg", side_effect=error
    ):
        with pytest.raises(WorkspaceBusy):
            with workspace_lease(tmp_path, "b" * 12):
                pytest.fail("Unconfirmed lease was replaced")

    assert lease_path.read_text() == original


def _write_unconfirmed_receipt(
    directory: Path, lease: WorkspaceLease, case: str
) -> None:
    _ = (directory / f"pre_commit_result_{lease.request_id}.json").write_text(
        json.dumps(
            {
                "owner": "2" * 64 if case == "wrong_owner" else lease.owner,
                "pid": lease.pgid,
                "status": "completed",
                "completed_at": time.time(),
                "workspace_completion_attempt": (
                    "3" * 32 if case == "reused_pid" else lease.attempt_id
                ),
            }
        )
    )
