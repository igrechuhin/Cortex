"""Fault injection and restart recovery tests for plan completion."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.core.file_system import FileSystemManager
from cortex.core.models import OperationStatus
from cortex.tools.plans import completion_transaction
from cortex.tools.plans.completion_transaction import run_completion_transaction
from cortex.tools.plans.completion_transaction_io import (
    completion_operations_root,
    operation_id,
    persist_payload,
    persist_record,
    read_record,
    record_path,
    write_owned_text,
)
from cortex.tools.plans.completion_transaction_models import (
    CompletionFileKey,
    CompletionOperationRecord,
    CompletionPhase,
)
from cortex.tools.plans.completion_transaction_prepare import (
    normalized_request,
    prepare_record,
)
from tests.tools.test_plan_completion_transaction import (
    CompletionFixture,
    assert_original,
    completion_request,
    seed_completion,
)


class RecordTamper(str, Enum):
    """Persisted record corruption modes exercised before recovery."""

    OPERATION_ID = "operation_id"
    FINGERPRINT = "fingerprint"
    FILE_SET = "file_set"
    PAYLOAD_NAME = "payload_name"
    PATH_TARGET = "path_target"


class PayloadTamper(str, Enum):
    """Payload integrity failures exercised before recovery."""

    BEFORE_CONTENT = "before_content"
    AFTER_CONTENT = "after_content"
    MISSING = "missing"
    DIRECTORY = "directory"
    SYMLINK = "symlink"


def _tamper_record(record: CompletionOperationRecord, tamper: RecordTamper) -> None:
    if tamper == RecordTamper.OPERATION_ID:
        record.operation_id = "0" * 24
    elif tamper == RecordTamper.FINGERPRINT:
        record.request_fingerprint = "invalid"
    elif tamper == RecordTamper.FILE_SET:
        record.files = [
            item for item in record.files if item.key != CompletionFileKey.ROADMAP
        ]
    elif tamper == RecordTamper.PAYLOAD_NAME:
        record.files[0].before_payload = "unexpected.before.txt"
    else:
        roadmap = next(
            item for item in record.files if item.key == CompletionFileKey.ROADMAP
        )
        roadmap.relative_path = roadmap.relative_path.replace(
            "roadmap.md", "progress.md"
        )


def _tamper_payload(
    operations: Path, record: CompletionOperationRecord, tamper: PayloadTamper
) -> None:
    item = record.files[0]
    payload_name = (
        item.after_payload
        if tamper == PayloadTamper.AFTER_CONTENT
        else item.before_payload
    )
    payload = operations / payload_name
    if tamper in {PayloadTamper.BEFORE_CONTENT, PayloadTamper.AFTER_CONTENT}:
        _ = payload.write_text("tampered", encoding="utf-8")
    elif tamper == PayloadTamper.MISSING:
        payload.unlink()
    elif tamper == PayloadTamper.DIRECTORY:
        payload.unlink()
        payload.mkdir()
    else:
        payload.unlink()
        target = operations / "tamper-target.txt"
        _ = target.write_text("tampered", encoding="utf-8")
        payload.symlink_to(target)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failed_name", ["sample.md", "roadmap.md", "activeContext.md", "progress.md"]
)
async def test_each_file_write_failure_rolls_back(
    tmp_path: Path, failed_name: str
) -> None:
    fixture = seed_completion(tmp_path)

    async def fail_one(
        manager: FileSystemManager,
        path: Path,
        content: str,
        expected_hash: str,
        expected_exists: bool,
    ) -> None:
        if path.name == failed_name:
            raise OSError(f"injected write failure: {failed_name}")
        await write_owned_text(manager, path, content, expected_hash, expected_exists)

    with patch.object(completion_transaction, "write_owned_text", new=fail_one):
        result = await run_completion_transaction(fixture.root, completion_request())

    assert result.status == OperationStatus.ERROR
    assert result.recovery_required is False
    assert_original(fixture)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "injected",
    [
        FileConflictError("roadmap.md", "sha256:old", "sha256:new"),
        FileLockTimeoutError("roadmap.md", 1),
        GitConflictError("roadmap.md"),
    ],
)
async def test_filesystem_exception_family_triggers_rollback(
    tmp_path: Path, injected: Exception
) -> None:
    fixture = seed_completion(tmp_path)

    async def fail_roadmap(
        manager: FileSystemManager,
        path: Path,
        content: str,
        expected_hash: str,
        expected_exists: bool,
    ) -> None:
        if path.name == "roadmap.md":
            raise injected
        await write_owned_text(manager, path, content, expected_hash, expected_exists)

    with patch.object(completion_transaction, "write_owned_text", new=fail_roadmap):
        result = await run_completion_transaction(fixture.root, completion_request())

    assert result.status == OperationStatus.ERROR
    assert_original(fixture)


@pytest.mark.asyncio
async def test_archive_failure_rolls_back_every_file(tmp_path: Path) -> None:
    fixture = seed_completion(tmp_path)

    with patch.object(
        completion_transaction, "_archive", side_effect=OSError("archive failed")
    ):
        result = await run_completion_transaction(fixture.root, completion_request())

    assert result.status == OperationStatus.ERROR
    assert_original(fixture)


@pytest.mark.asyncio
async def test_initial_record_failure_changes_no_product_file(tmp_path: Path) -> None:
    fixture = seed_completion(tmp_path)

    with patch.object(
        completion_transaction,
        "persist_record",
        side_effect=OSError("record unavailable"),
    ):
        result = await run_completion_transaction(fixture.root, completion_request())

    assert result.status == OperationStatus.ERROR
    assert_original(fixture)


@pytest.mark.asyncio
async def test_phase_record_failure_rolls_back(tmp_path: Path) -> None:
    fixture = seed_completion(tmp_path)

    with patch(
        "cortex.tools.plans.completion_transaction_io.persist_record",
        side_effect=OSError("phase record unavailable"),
    ):
        result = await run_completion_transaction(fixture.root, completion_request())

    assert result.status == OperationStatus.ERROR
    assert_original(fixture)


async def _interrupt_after_roadmap(fixture: CompletionFixture) -> None:
    async def interrupt(
        manager: FileSystemManager,
        path: Path,
        content: str,
        expected_hash: str,
        expected_exists: bool,
    ) -> None:
        if path.name == "activeContext.md":
            raise KeyboardInterrupt("simulated process interruption")
        await write_owned_text(manager, path, content, expected_hash, expected_exists)

    with patch.object(completion_transaction, "write_owned_text", new=interrupt):
        with pytest.raises(KeyboardInterrupt):
            _ = await run_completion_transaction(fixture.root, completion_request())


@pytest.mark.asyncio
async def test_restart_recovers_interruption_then_completes(tmp_path: Path) -> None:
    fixture = seed_completion(tmp_path)
    await _interrupt_after_roadmap(fixture)

    result = await run_completion_transaction(fixture.root, completion_request())

    assert result.status == OperationStatus.SUCCESS
    assert not fixture.plan.exists()
    assert fixture.active.read_text(encoding="utf-8").count("**Sample**") == 1
    assert fixture.progress.read_text(encoding="utf-8").count("**Sample**") == 1


@pytest.mark.asyncio
async def test_recovery_conflict_preserves_unrelated_edit(tmp_path: Path) -> None:
    fixture = seed_completion(tmp_path)
    await _interrupt_after_roadmap(fixture)
    with fixture.roadmap.open("a", encoding="utf-8") as stream:
        _ = stream.write("- **Concurrent** - PENDING\n")

    result = await run_completion_transaction(fixture.root, completion_request())

    assert result.status == OperationStatus.ERROR
    assert result.recovery_required is True
    assert "Concurrent" in fixture.roadmap.read_text(encoding="utf-8")
    assert result.operation_id is not None
    assert record_path(
        completion_operations_root(fixture.root), result.operation_id
    ).exists()


@pytest.mark.asyncio
async def test_concurrent_mutation_during_write_is_not_overwritten(
    tmp_path: Path,
) -> None:
    fixture = seed_completion(tmp_path)

    async def mutate_then_write(
        manager: FileSystemManager,
        path: Path,
        content: str,
        expected_hash: str,
        expected_exists: bool,
    ) -> None:
        if path.name == "roadmap.md":
            with path.open("a", encoding="utf-8") as stream:
                _ = stream.write("- **Concurrent** - PENDING\n")
        await write_owned_text(manager, path, content, expected_hash, expected_exists)

    with patch.object(
        completion_transaction, "write_owned_text", new=mutate_then_write
    ):
        result = await run_completion_transaction(fixture.root, completion_request())

    assert result.status == OperationStatus.ERROR
    assert result.recovery_required is True
    assert "Concurrent" in fixture.roadmap.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_tampered_archive_path_cannot_touch_external_file(tmp_path: Path) -> None:
    fixture = seed_completion(tmp_path)
    await _interrupt_after_roadmap(fixture)
    request = completion_request()
    path = record_path(completion_operations_root(fixture.root), operation_id(request))
    record = read_record(completion_operations_root(fixture.root), path)
    assert record is not None
    record.archive_destination = "../../sentinel.md"
    _ = path.write_text(record.model_dump_json(), encoding="utf-8")
    sentinel = tmp_path / "sentinel.md"
    _ = sentinel.write_text("preserve", encoding="utf-8")

    result = await run_completion_transaction(fixture.root, request)

    assert result.status == OperationStatus.ERROR
    assert result.recovery_required is True
    assert sentinel.read_text(encoding="utf-8") == "preserve"


@pytest.mark.asyncio
async def test_malformed_operation_record_is_rejected(tmp_path: Path) -> None:
    fixture = seed_completion(tmp_path)
    request = completion_request()
    operations = completion_operations_root(fixture.root)
    operations.mkdir(parents=True)
    path = record_path(operations, operation_id(request))
    _ = path.write_text("{}", encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    result = await run_completion_transaction(fixture.root, request)

    assert result.status == OperationStatus.ERROR
    assert result.recovery_required is True
    assert result.operation_id == operation_id(request)
    assert "manual recovery required" in result.message
    assert "Malformed completion operation record" in (result.error or "")
    assert path.read_text(encoding="utf-8") == before
    assert_original(fixture)


@pytest.mark.asyncio
async def test_symlink_operation_record_preserves_external_sentinel(
    tmp_path: Path,
) -> None:
    fixture = seed_completion(tmp_path)
    request = completion_request()
    operations = completion_operations_root(fixture.root)
    operations.mkdir(parents=True)
    path = record_path(operations, operation_id(request))
    sentinel = tmp_path / "record-sentinel.json"
    sentinel_content = '{"secret":"preserve"}'
    _ = sentinel.write_text(sentinel_content, encoding="utf-8")
    path.symlink_to(sentinel)

    result = await run_completion_transaction(fixture.root, request)

    assert result.status == OperationStatus.ERROR
    assert result.recovery_required is True
    assert "manual recovery required" in result.message
    assert path.is_symlink()
    assert sentinel.read_text(encoding="utf-8") == sentinel_content
    assert_original(fixture)


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper", list(RecordTamper))
async def test_inconsistent_operation_record_requires_recovery_without_mutation(
    tmp_path: Path, tamper: RecordTamper
) -> None:
    fixture = seed_completion(tmp_path)
    request = completion_request()
    operations = completion_operations_root(fixture.root)
    operations.mkdir(parents=True)
    path = record_path(operations, operation_id(request))
    record = prepare_record(fixture.root, operations, request)
    _tamper_record(record, tamper)
    persist_record(path, record)

    result = await run_completion_transaction(fixture.root, request)

    saved = read_record(operations, path)
    assert result.status == OperationStatus.ERROR
    assert result.recovery_required is True
    assert saved is not None
    assert saved.phase == CompletionPhase.RECOVERY_REQUIRED
    assert_original(fixture)


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper", list(PayloadTamper))
async def test_invalid_payload_requires_recovery_without_mutation(
    tmp_path: Path, tamper: PayloadTamper
) -> None:
    fixture = seed_completion(tmp_path)
    request = completion_request()
    operations = completion_operations_root(fixture.root)
    operations.mkdir(parents=True)
    path = record_path(operations, operation_id(request))
    record = prepare_record(fixture.root, operations, request)
    persist_record(path, record)
    _tamper_payload(operations, record, tamper)

    result = await run_completion_transaction(fixture.root, request)

    saved = read_record(operations, path)
    assert result.status == OperationStatus.ERROR
    assert result.recovery_required is True
    assert saved is not None
    assert saved.phase == CompletionPhase.RECOVERY_REQUIRED
    assert_original(fixture)


@pytest.mark.asyncio
async def test_payload_failure_is_cleaned_on_successful_retry(tmp_path: Path) -> None:
    fixture = seed_completion(tmp_path)
    real_persist = persist_payload
    calls = 0

    def fail_second(path: Path, content: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("payload failed")
        real_persist(path, content)

    with patch(
        "cortex.tools.plans.completion_transaction_prepare.persist_payload",
        new=fail_second,
    ):
        first = await run_completion_transaction(fixture.root, completion_request())
    second = await run_completion_transaction(fixture.root, completion_request())

    assert first.status == OperationStatus.ERROR
    assert second.status == OperationStatus.SUCCESS


@pytest.mark.asyncio
async def test_conflicting_retry_after_failure_is_rejected(tmp_path: Path) -> None:
    fixture = seed_completion(tmp_path)
    with patch.object(
        completion_transaction, "_archive", side_effect=OSError("archive failed")
    ):
        first = await run_completion_transaction(fixture.root, completion_request())

    second = await run_completion_transaction(
        fixture.root,
        normalized_request("Sample", "Changed", "2026-09-08", None, "sample.md"),
    )

    assert first.status == OperationStatus.ERROR
    assert second.status == OperationStatus.ERROR
    assert "Conflicting" in second.message
