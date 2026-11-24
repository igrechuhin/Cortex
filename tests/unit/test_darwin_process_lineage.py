"""Kernel inventory regressions for verified SwiftPM timeout teardown."""

from unittest.mock import MagicMock, patch

import pytest

from cortex.services.framework_adapters.darwin_process_lineage import (
    DarwinProcessLineage,
    ProcessIdentity,
)

_MODULE = "cortex.services.framework_adapters.darwin_process_lineage"
_INIT = ProcessIdentity(1, 0, 1, 0)
_OLDER = ProcessIdentity(10, 1, 20, 1)


@pytest.mark.parametrize(
    "process,verified",
    [
        (ProcessIdentity(30, 10, 60, 20), True),
        (ProcessIdentity(30, 20, 60, 40), False),
        (ProcessIdentity(30, 25, 60, 50), False),
        (ProcessIdentity(30, 1, 60, 50), False),
        (ProcessIdentity(20, 10, 40, 20), False),
    ],
    ids=["unrelated", "live-child", "orphan", "orphan-exec", "unreaped-launcher"],
)
def test_only_verified_unrelated_lineage_allows_recovery(
    process: ProcessIdentity, verified: bool
) -> None:
    lineage = DarwinProcessLineage(MagicMock())
    with (
        patch(f"{_MODULE}._VERIFY_SECONDS", 0),
        patch.object(
            lineage, "_stable_inventory", return_value=[_INIT, _OLDER, process]
        ),
    ):
        assert lineage.verify_after_reap(20) is verified


@pytest.mark.parametrize("second", [None, ProcessIdentity(30, 10, 60, 20)])
def test_pid_disappearance_or_reuse_invalidates_inventory(
    second: ProcessIdentity | None,
) -> None:
    lineage = DarwinProcessLineage(MagicMock())
    with (
        patch(f"{_MODULE}._VERIFY_SECONDS", 0),
        patch.object(lineage, "_live_pids", return_value=[1, 10]),
        patch.object(
            lineage, "_read_identity", side_effect=[_INIT, _OLDER, _INIT, second]
        ),
    ):
        assert not lineage.verify_after_reap(20)
