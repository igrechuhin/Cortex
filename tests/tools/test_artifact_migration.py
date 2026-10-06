"""Temporary-only migration evidence, including exact 18-report relocation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_cache import (
    add_version_to_history_impl,
    finalize_file_metadata_update_impl,
)
from cortex.core.metadata_index import MetadataIndex
from cortex.core.metadata_queries import validate_index_consistency_from_data
from cortex.core.token_counter import TokenCounter
from cortex.managers.types import ManagersDict
from cortex.memory.temporal_store import (
    TemporalFact,
    TemporalFactCategory,
    TemporalMemoryStore,
)
from cortex.refactoring.version_snapshots import file_has_snapshot, get_version_history
from cortex.tools.files import artifact_migration as engine
from cortex.tools.files.artifact_migration_io import persist, receipt_path, write_bytes
from cortex.tools.files.artifact_migration_models import MigrationPhase, MigrationRecord
from cortex.tools.files.artifact_migration_prepare import byte_hash, prepare_migration


def _write(root: Path, relative: str, content: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_bytes(content)
    return path


def _managers(root: Path) -> ManagersDict:
    tokens = TokenCounter()
    tokens.tiktoken_available = False
    return ManagersDict.model_construct(
        fs=FileSystemManager(root),
        index=MetadataIndex(root),
        tokens=tokens,
        graph=DependencyGraph(),
    )


def _reports(root: Path) -> dict[str, bytes]:
    reports: dict[str, bytes] = {}
    for directory, count in (("reviews", 13), ("analyses", 4), ("queries", 1)):
        for number in range(count):
            name = f"{directory}/report-{number}{'-2' if number == 1 else ''}.md"
            content = (
                f"# Report {number}\r\n\r\nAuthored body, {directory}.\r\n".encode()
            )
            reports[name] = content
            _ = _write(root, ".cortex/memory-bank/" + name, content)
    return reports


def _index(root: Path, mgrs: ManagersDict, reports: dict[str, bytes]) -> None:
    data = mgrs.index.create_empty_index()
    files: dict[str, object] = {}
    for relative, content in reports.items():
        files[relative] = {
            "path": ".cortex/memory-bank/" + relative,
            "exists": True,
            "size_bytes": len(content),
            "token_count": 5,
            "token_model": "cl100k_base",
            "last_modified": "2026-01-01",
            "content_hash": byte_hash(content),
            "sections": [],
            "read_count": 7,
            "write_count": 3,
            "current_version": 9,
            "version_history": [
                {"path": ".cortex/memory-bank/" + relative, "version": 9}
            ],
        }
    data["files"] = files
    _ = _write(root, ".cortex/index.json", json.dumps(data).encode())


def _fixture(root: Path) -> tuple[ManagersDict, dict[str, bytes], TemporalMemoryStore]:
    mgrs = _managers(root)
    reports = _reports(root)
    _index(root, mgrs, reports)
    _ = _write(
        root,
        ".cortex/memory-bank/activeContext.md",
        b"# Context\r\n[Review](reviews/report-0.md#issues)\r\n",
    )
    _ = _write(root, ".cortex/memory-bank/findings/finding.md", b"# Finding\n")
    _ = _write(
        root,
        ".cortex/wiki/analyses/mirror.md",
        b"# Mirror\r\nAuthored report mirror.\r\n",
    )
    return mgrs, reports, _seed_history(root)


def _seed_history(root: Path) -> TemporalMemoryStore:
    _ = _write(
        root,
        ".cortex/wiki/sources/snapshot.md",
        b"[Historical](../../memory-bank/reviews/report-0.md)\n",
    )
    _ = _write(
        root,
        ".cortex/history/report-0/9.md",
        b"[Historical](../../memory-bank/reviews/report-0.md)\n",
    )
    _ = _write(
        root,
        ".cortex/wal/write_log.jsonl",
        b'{"historical":".cortex/memory-bank/reviews/report-0.md"}\n',
    )
    store = TemporalMemoryStore(root / ".cortex/temporal.db")
    store.add_fact(
        TemporalFact(
            category=TemporalFactCategory.STATUS,
            subject="report-0",
            predicate="status",
            object="reviewed",
            valid_from="2026-01-01",
            source_file=".cortex/memory-bank/reviews/report-0.md",
            source_line=1,
        )
    )
    return store


def _bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ".session" not in path.parts
    }


async def test_preview_is_read_only_and_moves_exactly_eighteen_reports(
    tmp_path: Path,
) -> None:
    mgrs, reports, _ = _fixture(tmp_path)
    before = _bytes(tmp_path)
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    assert preview["status"] == "success"
    assert preview["apply"] is False
    assert preview["migration_count"] == 18
    assert len(preview["preview_digest"]) == 64
    assert _bytes(tmp_path) == before
    assert not (tmp_path / ".cortex/.session").exists()
    assert {item["source"] for item in preview["relocations"]} == {
        ".cortex/memory-bank/" + name for name in reports
    }


def _assert_provenance(
    root: Path, store: TemporalMemoryStore, facts: list[dict[str, object]]
) -> None:
    all_facts = store.all_facts()
    assert [
        fact.model_dump() for fact in all_facts if fact.predicate != "relocated_to"
    ] == facts
    assert len([fact for fact in all_facts if fact.predicate == "relocated_to"]) == 18
    assert (
        len((root / ".cortex/wal/artifact_relocations.jsonl").read_bytes().splitlines())
        == 18
    )


async def _apply(root: Path, mgrs: ManagersDict, digest: str) -> str:
    return await engine.migrate_artifacts(
        root, mgrs, apply=True, expected_preview_digest=digest
    )


async def test_apply_preserves_hashes_identity_mirrors_history_and_appends_facts(
    tmp_path: Path,
) -> None:
    mgrs, reports, store = _fixture(tmp_path)
    before = _bytes(tmp_path)
    facts = [fact.model_dump() for fact in store.all_facts()]
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    result = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
    assert result["status"] == "success"
    for relative, content in reports.items():
        assert (tmp_path / ".cortex" / relative).read_bytes() == content
    _assert_metadata(tmp_path, reports)
    assert (
        tmp_path / ".cortex/memory-bank/activeContext.md"
    ).read_bytes() == b"# Context\r\n[Review](../reviews/report-0.md#issues)\r\n"
    for relative in (
        ".cortex/wiki/analyses/mirror.md",
        ".cortex/wiki/sources/snapshot.md",
        ".cortex/history/report-0/9.md",
        ".cortex/wal/write_log.jsonl",
        ".cortex/memory-bank/findings/finding.md",
    ):
        assert (tmp_path / relative).read_bytes() == before[relative]
    _assert_provenance(tmp_path, store, facts)
    assert all(
        not (tmp_path / ".cortex/memory-bank" / name).exists()
        for name in ("reviews", "analyses", "queries")
    )
    assert mgrs.graph.dynamic_deps == {}


def _assert_metadata(root: Path, reports: dict[str, bytes]) -> None:
    files = json.loads((root / ".cortex/index.json").read_bytes())["files"]
    assert set(files) == set(reports)
    for relative, content in reports.items():
        meta = files[relative]
        assert meta["path"] == ".cortex/" + relative
        assert meta["content_hash"] == byte_hash(content)
        assert meta["current_version"] == 9
        assert meta["read_count"] == 7
        assert meta["write_count"] == 3
        assert meta["version_history"] == [
            {"path": ".cortex/memory-bank/" + relative, "version": 9}
        ]


async def test_replay_after_subsequent_filing_is_idempotent(tmp_path: Path) -> None:
    mgrs, _, store = _fixture(tmp_path)
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    digest = preview["preview_digest"]
    assert json.loads(await _apply(tmp_path, mgrs, digest))["status"] == "success"
    _ = _write(
        tmp_path, ".cortex/reviews/new-valid-report.md", b"# Subsequent filing\n"
    )
    _ = _write(
        tmp_path,
        ".cortex/memory-bank/activeContext.md",
        b"# New context\n[New](../reviews/new-valid-report.md)\n",
    )
    before = _bytes(tmp_path)
    result = json.loads(await _apply(tmp_path, mgrs, digest))
    assert result["status"] == "success"
    assert result["replayed"] is True
    assert _bytes(tmp_path) == before
    assert len(store.all_facts()) == 19
    assert (
        json.loads(await engine.migrate_artifacts(tmp_path, mgrs))["migration_count"]
        == 0
    )


def _change_preview_input(root: Path, store: TemporalMemoryStore, changed: str) -> None:
    paths = {
        "source": ".cortex/memory-bank/reviews/report-0.md",
        "reference": ".cortex/memory-bank/activeContext.md",
        "index": ".cortex/index.json",
        "destination": ".cortex/reviews/other.md",
        "history": ".cortex/history/report-0/9.md",
    }
    if changed == "temporal":
        store.add_fact(
            TemporalFact(
                category=TemporalFactCategory.STATUS,
                subject="new",
                predicate="status",
                object="open",
                valid_from="2026-01-01",
                source_file="new",
                source_line=1,
            )
        )
    else:
        path = paths[changed]
        if changed == "index":
            content = json.loads((root / path).read_bytes())
            content["last_updated"] = "changed"
            _ = _write(root, path, json.dumps(content).encode())
        else:
            _ = _write(root, path, b"changed\n")


@pytest.mark.parametrize(
    "changed", ["source", "reference", "index", "destination", "history", "temporal"]
)
async def test_stale_digest_refuses_before_mutation(
    tmp_path: Path, changed: str
) -> None:
    mgrs, _, store = _fixture(tmp_path)
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    _change_preview_input(tmp_path, store, changed)
    before = _bytes(tmp_path)
    result = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
    assert result["status"] == "error"
    assert "Stale" in result["error"]
    assert _bytes(tmp_path) == before
    assert not (tmp_path / ".cortex/.session").exists()


@pytest.mark.parametrize("directory", ["memory-bank/reviews", "reviews"])
async def test_collision_and_symlink_refuse_without_mutation(
    tmp_path: Path, directory: str
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    target = tmp_path / ".cortex" / directory / "unsafe.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(tmp_path / ".cortex/memory-bank/reviews/report-0.md")
    before = _bytes(tmp_path)
    assert (
        json.loads(await engine.migrate_artifacts(tmp_path, mgrs))["status"] == "error"
    )
    assert _bytes(tmp_path) == before
    target.unlink()
    _ = _write(tmp_path, ".cortex/reviews/report-0.md", b"collision")
    before = _bytes(tmp_path)
    result = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    assert "collision" in result["error"]
    assert _bytes(tmp_path) == before


async def test_traversal_index_and_digest_are_rejected(tmp_path: Path) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    path = tmp_path / ".cortex/index.json"
    data = json.loads(path.read_bytes())
    data["files"]["reviews/report-0.md"]["path"] = "../outside.md"
    _ = path.write_text(json.dumps(data))
    before = _bytes(tmp_path)
    assert (
        json.loads(await engine.migrate_artifacts(tmp_path, mgrs))["status"] == "error"
    )
    assert json.loads(await _apply(tmp_path, mgrs, "../unsafe"))["status"] == "error"
    assert _bytes(tmp_path) == before


async def test_write_failure_rolls_back_exact_bytes_and_retry_succeeds(
    tmp_path: Path,
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    before = _bytes(tmp_path)
    original = write_bytes
    calls = 0

    def fail_once(root: Path, relative: str, content: bytes | None) -> None:
        nonlocal calls
        calls += 1
        if calls == 5:
            raise OSError("injected disk failure")
        original(root, relative, content)

    with patch(
        "cortex.tools.files.artifact_migration._write_bytes", side_effect=fail_once
    ):
        result = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
    assert result["status"] == "error"
    assert _bytes(tmp_path) == before
    retry = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
    assert retry["status"] == "success"


async def test_interrupted_prepared_transaction_recovers_without_loss(
    tmp_path: Path,
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    plan = prepare_migration(tmp_path, mgrs)
    receipt = receipt_path(tmp_path, plan.digest)
    record = MigrationRecord(
        phase=MigrationPhase.PREPARED,
        plan=plan,
        created_at="2026-10-05T12:00:00+00:00",
        writes_started=True,
    )
    persist(receipt, record)
    for item in plan.edits[:3]:
        write_bytes(tmp_path, item.path, item.after)
    record.created_directories = [
        relative
        for relative, state in plan.snapshot.items()
        if state == "absent_directory" and (tmp_path / relative).is_dir()
    ]
    persist(receipt, record)
    result = json.loads(await _apply(tmp_path, mgrs, plan.digest))
    assert result["status"] == "success"
    assert len(list((tmp_path / ".cortex/reviews").glob("*.md"))) == 13


async def test_outgoing_incoming_wiki_links_and_code_are_rewritten_minimally(
    tmp_path: Path,
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    report = b'# Report\r\n[Context](../activeContext.md "title")\r\n[Sibling](report-1-2.md#notes)\r\n{{include: ../analyses/report-0.md#one|lines=3}}\r\n'
    _ = _write(tmp_path, ".cortex/memory-bank/reviews/report-0.md", report)
    wiki = b"# Mirror\n[Review](../../memory-bank/reviews/report-0.md#notes)\n`[Code](../../memory-bank/reviews/report-0.md)`\n"
    _ = _write(tmp_path, ".cortex/wiki/analyses/mirror.md", wiki)
    _ = _write(
        tmp_path,
        "notes.md",
        b'[Review][r]\n[r]: .cortex/memory-bank/reviews/report-0.md "title"\n',
    )
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    result = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
    assert result["status"] == "success"
    assert (tmp_path / ".cortex/reviews/report-0.md").read_bytes() == report.replace(
        b"../activeContext.md", b"../memory-bank/activeContext.md"
    )
    assert (tmp_path / ".cortex/wiki/analyses/mirror.md").read_bytes() == wiki.replace(
        b"[Review](../../memory-bank/reviews/", b"[Review](../../reviews/"
    )
    assert (
        tmp_path / "notes.md"
    ).read_bytes() == b'[Review][r]\n[r]: .cortex/reviews/report-0.md "title"\n'
    files = json.loads((tmp_path / ".cortex/index.json").read_bytes())["files"]
    assert files["reviews/report-0.md"]["content_hash"] == byte_hash(
        (tmp_path / ".cortex/reviews/report-0.md").read_bytes()
    )


async def test_apply_requires_digest_and_completed_provenance_resumes(
    tmp_path: Path,
) -> None:
    mgrs, _, store = _fixture(tmp_path)
    assert (
        json.loads(await engine.migrate_artifacts(tmp_path, mgrs, apply=True))["status"]
        == "error"
    )
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    with patch.object(
        engine, "_append_provenance", side_effect=OSError("provenance unavailable")
    ):
        result = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
    assert result["status"] == "error"
    assert (tmp_path / ".cortex/reviews/report-0.md").exists()
    retry = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
    assert retry["status"] == "success"
    assert len(store.all_facts()) == 19


async def test_preview_digest_is_stable_and_binary_variants_are_preserved(
    tmp_path: Path,
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    binary = b"\x00\xff\x80\r\n"
    _ = _write(tmp_path, ".cortex/memory-bank/queries/nested/variant.bin", binary)
    first = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    second = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    assert first["preview_digest"] == second["preview_digest"]
    result = json.loads(await _apply(tmp_path, mgrs, first["preview_digest"]))
    assert result["status"] == "success"
    assert (tmp_path / ".cortex/queries/nested/variant.bin").read_bytes() == binary
    assert (tmp_path / ".cortex/memory-bank/queries/nested").is_dir()


async def test_absolute_local_links_relocate_and_external_authored_links_stay(
    tmp_path: Path,
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    old = tmp_path / ".cortex/memory-bank/reviews/report-1-2.md"
    report = f"# Report\n[Local]({old}#anchor)\n[External](/outside/report.md)\n[Web](https://example.com/report.md)\n".encode()
    _ = _write(tmp_path, ".cortex/memory-bank/reviews/report-0.md", report)
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    result = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
    assert result["status"] == "success"
    assert (tmp_path / ".cortex/reviews/report-0.md").read_bytes() == report.replace(
        str(old).encode(), str(tmp_path / ".cortex/reviews/report-1-2.md").encode()
    )


async def test_tampered_receipt_rejects_before_any_mutation(tmp_path: Path) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    plan = prepare_migration(tmp_path, mgrs)
    receipt = receipt_path(tmp_path, plan.digest)
    record = MigrationRecord(
        phase=MigrationPhase.PREPARED, plan=plan, created_at="2026-10-05T12:00:00+00:00"
    )
    persist(receipt, record)
    raw = json.loads(receipt.read_bytes())
    raw["plan"]["edits"][0]["path"] = "../outside.md"
    _ = receipt.write_text(json.dumps(raw))
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    result = json.loads(await _apply(tmp_path, mgrs, plan.digest))
    assert result["status"] == "error"
    assert {
        path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()
    } == before


@pytest.mark.parametrize("fail", [False, True])
async def test_old_lock_named_artifact_is_never_used_as_lock(
    tmp_path: Path, fail: bool
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    payload = b"Existing canonical artifact variant, not an operation lock.\n"
    variant = _write(tmp_path, ".cortex/reviews/report-0.md.lock", payload)
    os.utime(variant, (1, 1))
    before = _bytes(tmp_path)
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    if fail:
        with patch(
            "cortex.tools.files.artifact_migration._write_bytes",
            side_effect=OSError("injected"),
        ):
            result = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
        assert result["status"] == "error"
        assert _bytes(tmp_path) == before
    else:
        result = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
        assert result["status"] == "success"
    assert variant.read_bytes() == payload


async def test_balanced_angle_and_escaped_variant_links_exclude_code(
    tmp_path: Path,
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    _ = _write(tmp_path, ".cortex/memory-bank/reviews/report(1).md", b"# Variant\n")
    _ = _write(tmp_path, ".cortex/memory-bank/reviews/report).md", b"# Escaped\n")
    incoming = (
        "[Bare](reviews/report(1).md#notes)\n"
        "[Angle](<reviews/report(1).md>)\n"
        "[Escaped](reviews/report\\(1\\).md)\n"
        "[Unbalanced](reviews/report\\).md)\n"
        '[Reference][r]\n[r]: <reviews/report(1).md> "title"\n'
        "    [Indented](reviews/report(1).md)\n"
        "\t[Tabbed](reviews/report(1).md)\n"
        "`[Inline](reviews/report(1).md)`\n"
        "\\[Literal](reviews/report(1).md)\n"
        "```markdown\n[Fenced](reviews/report(1).md)\n```\n"
    ).encode()
    context = _write(tmp_path, ".cortex/memory-bank/activeContext.md", incoming)
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    result = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
    assert result["status"] == "success"
    expected = (
        incoming.replace(b"[Bare](reviews/", b"[Bare](../reviews/")
        .replace(b"[Angle](<reviews/", b"[Angle](<../reviews/")
        .replace(b"[Escaped](reviews/", b"[Escaped](../reviews/")
        .replace(b"[Unbalanced](reviews/", b"[Unbalanced](../reviews/")
        .replace(b"[r]: <reviews/", b"[r]: <../reviews/")
    )
    assert context.read_bytes() == expected
    assert (tmp_path / ".cortex/reviews/report(1).md").read_bytes() == b"# Variant\n"


@pytest.mark.parametrize(
    "relative",
    [
        ".github/workflows/guide.md",
        ".claude/commands/guide.md",
        ".agents/commands/guide.md",
        "docs/history/guide.md",
    ],
)
async def test_hidden_authored_references_are_updated(
    tmp_path: Path, relative: str
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    incoming = b"[Review](../../.cortex/memory-bank/reviews/report-0.md)\n"
    path = _write(tmp_path, relative, incoming)
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    result = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
    assert result["status"] == "success"
    assert path.read_bytes() == incoming.replace(
        b".cortex/memory-bank/reviews/", b".cortex/reviews/"
    )


@pytest.mark.parametrize("relative", [".cortex/rules", ".cortex/synapse"])
async def test_shared_rule_trees_are_untouched_during_preview_and_apply(
    tmp_path: Path, relative: str
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    external = tmp_path.parent / (tmp_path.name + "-shared-code")
    external.mkdir()
    original = (
        f"[Report]({tmp_path}/.cortex/memory-bank/reviews/report-0.md)\n".encode()
    )
    target = external / "rule.md"
    _ = target.write_bytes(original)
    pointer = tmp_path / relative
    pointer.symlink_to(external, target_is_directory=True)
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    assert preview["migration_count"] == 18
    assert target.read_bytes() == original
    assert not any(path.startswith(relative) for path in preview["reference_updates"])
    result = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
    assert result["status"] == "success" and result["migration_count"] == 18
    assert pointer.is_symlink() and pointer.readlink() == external
    assert target.read_bytes() == original


def _generated_framework(root: Path, relative: str) -> tuple[Path, bytes]:
    original = f"[Report]({root}/.cortex/memory-bank/reviews/report-0.md)\n".encode()
    path = _write(
        root,
        f"{relative}/ArgumentParser.framework/Versions/A/Headers/guide.md",
        original,
    )
    (root / relative / "ArgumentParser.framework/Headers").symlink_to(
        "Versions/A/Headers", target_is_directory=True
    )
    _ = _write(root, f"{relative}/README.md", original)
    return path, original


@pytest.mark.parametrize(
    "relative",
    [
        "Build",
        ".build",
        ".swiftpm",
        "DerivedData",
        "Derived",
        "Build.rollback",
        "ModelTraining/Outputs",
        "Sources",
        "Tests",
        "Dependencies/A.framework",
    ],
)
async def test_generated_frameworks_are_not_reference_inputs(
    tmp_path: Path, relative: str
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    target, original = _generated_framework(tmp_path, relative)
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    assert preview["migration_count"] == 18
    assert not any(path.startswith(relative) for path in preview["reference_updates"])
    result = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
    assert result["status"] == "success" and result["migration_count"] == 18
    assert target.read_bytes() == original
    assert (tmp_path / relative / "README.md").read_bytes() == original
    assert (tmp_path / relative / "ArgumentParser.framework/Headers").is_symlink()


async def test_git_ignore_bounds_generated_inputs_without_losing_cortex_references(
    tmp_path: Path,
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    target, original = _generated_framework(tmp_path, "MachineOutput")
    _ = subprocess.run(
        ["git", "init", "-q", str(tmp_path)], check=True, capture_output=True
    )
    _ = _write(
        tmp_path, ".gitignore", b"/MachineOutput/\n/.cortex/wiki/\n/.cortex/reviews/\n"
    )
    wiki = _write(
        tmp_path,
        ".cortex/wiki/guide.md",
        b"[Report](../memory-bank/reviews/report-0.md)\n",
    )
    authored = _write(
        tmp_path,
        "docs/reference.MD",
        b"[Report](../.cortex/memory-bank/reviews/report-0.md)\n",
    )
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    assert preview["migration_count"] == 18
    updates = preview["reference_updates"]
    assert not any(path.startswith("MachineOutput/") for path in updates)
    result = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
    assert result["status"] == "success"
    assert target.read_bytes() == original
    assert (tmp_path / "MachineOutput/README.md").read_bytes() == original
    assert wiki.read_bytes() == b"[Report](../reviews/report-0.md)\n"
    assert authored.read_bytes() == b"[Report](../.cortex/reviews/report-0.md)\n"


async def test_reference_markdown_symlink_still_refuses_before_mutation(
    tmp_path: Path,
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    original = _bytes(tmp_path)
    target = tmp_path.parent / (tmp_path.name + "-external.md")
    _ = target.write_bytes(b"Unchanged authored reference outside the workspace.\n")
    (tmp_path / "reference.md").symlink_to(target)
    result = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    assert result["status"] == "error" and "symlink" in result["error"]
    for path, content in original.items():
        assert (tmp_path / path).read_bytes() == content
    assert (
        target.read_bytes() == b"Unchanged authored reference outside the workspace.\n"
    )


async def test_generated_skill_and_workspace_symlinks_are_excluded(
    tmp_path: Path,
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    external = tmp_path.parent / (tmp_path.name + "-installed")
    external.mkdir()
    for relative in (
        ".cortex/skills",
        ".agents/skills",
        ".claude/skills",
        ".build",
        ".swiftpm",
        "DerivedData",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(external, target_is_directory=True)
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    assert preview["status"] == "success"
    assert preview["migration_count"] == 18


@pytest.mark.parametrize(
    "new_path",
    [
        "notes.md",
        ".cortex/reviews/new.md",
        ".cortex/memory-bank/queries/new.md",
        ".cortex/reviews/empty-directory",
        ".cortex/reviews",
    ],
)
async def test_membership_changes_during_lock_wait_refuse_approved_plan(
    tmp_path: Path, new_path: str
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    original = mgrs.fs.acquire_lock
    inserted = False

    async def acquire_with_intervening_addition(path: Path) -> None:
        nonlocal inserted
        if path.parent.name == "locks" and not inserted:
            inserted = True
            if new_path.endswith("empty-directory") or new_path == ".cortex/reviews":
                (tmp_path / new_path).mkdir(parents=True)
            else:
                _ = _write(
                    tmp_path,
                    new_path,
                    b"[New](.cortex/memory-bank/reviews/report-0.md)\n",
                )
        await original(path)

    with patch.object(
        mgrs.fs, "acquire_lock", side_effect=acquire_with_intervening_addition
    ):
        result = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
    assert result["status"] == "error"
    assert (tmp_path / ".cortex/memory-bank/reviews/report-0.md").exists()
    assert not (tmp_path / ".cortex/reviews/report-0.md").exists()
    assert (tmp_path / new_path).exists()


async def test_nested_destination_ancestor_file_collision_is_read_only(
    tmp_path: Path,
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    _ = _write(tmp_path, ".cortex/memory-bank/reviews/batch/report.md", b"# Nested\n")
    _ = _write(tmp_path, ".cortex/reviews/batch", b"Existing file, not a directory.\n")
    before = _bytes(tmp_path)
    result = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    assert result["status"] == "error"
    assert "ancestor collision" in result["error"]
    assert _bytes(tmp_path) == before
    assert not (tmp_path / ".cortex/.session").exists()


async def _root_bound_fixture(root: Path, include_receipt: bool) -> str:
    root.mkdir()
    mgrs, _, _ = _fixture(root)
    preview = json.loads(await engine.migrate_artifacts(root, mgrs))
    assert preview["project_root"] == str(root.resolve())
    digest = preview["preview_digest"]
    if include_receipt:
        persist(
            receipt_path(root, digest),
            MigrationRecord(
                phase=MigrationPhase.PREPARED,
                plan=prepare_migration(root, mgrs),
                created_at="2026-10-05T12:00:00+00:00",
            ),
        )
    return digest


@pytest.mark.parametrize("include_receipt", [False, True])
async def test_approved_digest_is_bound_to_the_exact_resolved_root(
    tmp_path: Path, include_receipt: bool
) -> None:
    original = tmp_path / "original"
    digest = await _root_bound_fixture(original, include_receipt)
    copied = tmp_path / "copied"
    _ = shutil.copytree(original, copied)
    copied_mgrs = _managers(copied)
    before = _bytes(copied)
    result = json.loads(await _apply(copied, copied_mgrs, digest))
    assert result["status"] == "error"
    assert result["project_root"] == str(copied.resolve())
    assert _bytes(copied) == before
    if include_receipt:
        assert (
            receipt_path(copied, digest).read_bytes()
            == receipt_path(original, digest).read_bytes()
        )
    else:
        assert not (copied / ".cortex/.session").exists()
    assert (
        json.loads(await engine.migrate_artifacts(copied, copied_mgrs))[
            "preview_digest"
        ]
        != digest
    )


async def test_public_metadata_cache_invalidation_is_exercised(tmp_path: Path) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    with patch.object(
        mgrs.index, "invalidate_cache", wraps=mgrs.index.invalidate_cache
    ) as invalidate:
        result = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
    assert result["status"] == "success"
    invalidate.assert_called_once()


@pytest.mark.parametrize("change", ["delete_source", "create_destination"])
async def test_pre_write_rejection_never_rolls_back_external_changes(
    tmp_path: Path, change: str
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    acquire = mgrs.fs.acquire_lock
    intervening: dict[str, bytes] | None = None

    async def acquire_after_external_change(path: Path) -> None:
        nonlocal intervening
        if path.parent.name == "locks" and intervening is None:
            source = tmp_path / ".cortex/memory-bank/reviews/report-0.md"
            if change == "delete_source":
                source.unlink()
            else:
                _ = _write(tmp_path, ".cortex/reviews/report-0.md", source.read_bytes())
            intervening = _bytes(tmp_path)
        await acquire(path)

    with patch.object(
        mgrs.fs, "acquire_lock", side_effect=acquire_after_external_change
    ):
        result = json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))
    assert result["status"] == "error"
    assert intervening is not None
    assert _bytes(tmp_path) == intervening


def _index_files(root: Path) -> dict[str, dict[str, object]]:
    return cast(
        dict[str, dict[str, object]],
        json.loads((root / ".cortex/index.json").read_bytes())["files"],
    )


def _retained_metadata(
    template: dict[str, object],
    identity: str,
    relative: str,
    content: bytes,
) -> dict[str, object]:
    metadata = dict(template)
    metadata.update(
        {
            "path": relative,
            "size_bytes": len(content),
            "content_hash": byte_hash(content),
            "current_version": 4,
            "version_history": [{"version": 4, "path": ".cortex/history/" + identity}],
        }
    )
    return metadata


def _seed_retained_rows(root: Path) -> None:
    path = root / ".cortex/index.json"
    data = json.loads(path.read_bytes())
    template = data["files"]["reviews/report-0.md"]
    entries = (
        ("retained-finding", ".cortex/memory-bank/findings/finding.md", b"# Finding\n"),
        (
            "retained-canonical",
            ".cortex/reviews/existing.md",
            b"# Existing canonical\n",
        ),
    )
    for identity, relative, content in entries:
        _ = _write(root, relative, content)
        data["files"][identity] = _retained_metadata(
            template, identity, relative, content
        )
    _ = path.write_bytes(json.dumps(data).encode())


def _seed_stale_row(root: Path) -> None:
    path = root / ".cortex/index.json"
    data = json.loads(path.read_bytes())
    metadata = dict(data["files"]["reviews/report-0.md"])
    metadata["path"] = ".cortex/reviews/physically-missing.md"
    data["files"]["physically-missing"] = metadata
    _ = path.write_bytes(json.dumps(data).encode())


async def _assert_loaded_entries(
    index: MetadataIndex, expected: dict[str, dict[str, object]]
) -> None:
    assert (await index.load())["files"] == expected
    for identity, row in expected.items():
        metadata = await index.get_file_metadata(identity)
        assert metadata is not None
        assert metadata.path == row["path"]
        assert metadata.content_hash == row["content_hash"]
        assert metadata.current_version == row["current_version"]
        assert metadata.version_history == row["version_history"]


def _protected_bytes(root: Path) -> dict[str, bytes]:
    paths = (
        ".cortex/wiki/sources/snapshot.md",
        ".cortex/history/report-0/9.md",
        ".cortex/wal/write_log.jsonl",
        ".cortex/memory-bank/findings/finding.md",
        ".cortex/reviews/existing.md",
    )
    return {relative: (root / relative).read_bytes() for relative in paths}


def _assert_index_history(
    original: dict[str, dict[str, object]],
    expected: dict[str, dict[str, object]],
) -> None:
    assert set(expected) == set(original)
    for identity, row in original.items():
        assert expected[identity]["version_history"] == row["version_history"]
    for identity in ("retained-finding", "retained-canonical"):
        assert expected[identity] == original[identity]


async def _assert_real_cleanup(
    root: Path, index: MetadataIndex, expected: dict[str, dict[str, object]]
) -> None:
    _seed_stale_row(root)
    index.invalidate_cache()
    assert await index.cleanup_stale_entries() == 1
    index.invalidate_cache()
    await _assert_loaded_entries(index, expected)
    assert _index_files(root) == expected


async def test_apply_reload_read_and_real_cleanup_preserve_identity_and_history(
    tmp_path: Path,
) -> None:
    mgrs, _, store = _fixture(tmp_path)
    _seed_retained_rows(tmp_path)
    original = _index_files(tmp_path)
    protected = _protected_bytes(tmp_path)
    preview = json.loads(await engine.migrate_artifacts(tmp_path, mgrs))
    assert (
        json.loads(await _apply(tmp_path, mgrs, preview["preview_digest"]))["status"]
        == "success"
    )
    expected = _index_files(tmp_path)
    _assert_index_history(original, expected)
    facts = [fact.model_dump() for fact in store.all_facts()]
    mgrs.index.invalidate_cache()
    await _assert_loaded_entries(mgrs.index, expected)
    assert await mgrs.index.validate_index_consistency() == []
    assert await mgrs.index.cleanup_stale_entries(dry_run=True) == 0
    await _assert_real_cleanup(tmp_path, mgrs.index, expected)
    assert _protected_bytes(tmp_path) == protected
    assert [fact.model_dump() for fact in store.all_facts()] == facts


async def test_metadata_update_and_version_increment_keep_existing_provenance(
    tmp_path: Path,
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    data = await mgrs.index.load()
    files = cast(dict[str, object], data["files"])
    history = _index_files(tmp_path)["reviews/report-0.md"]["version_history"]
    metadata = await mgrs.index.get_file_metadata("reviews/report-0.md")
    assert metadata is not None
    finalize_file_metadata_update_impl(
        data, files, "reviews/report-0.md", metadata, "internal", "2026-10-05"
    )
    add_version_to_history_impl(data, "reviews/report-0.md", {"version": 10})
    await mgrs.index.save()
    mgrs.index.invalidate_cache()
    _ = await mgrs.index.load()
    row = _index_files(tmp_path)["reviews/report-0.md"]
    assert row["version_history"] == history
    assert row["current_version"] == 10
    assert row["last_read"] == "2026-10-05"


@pytest.mark.parametrize(
    "stored",
    ["legacy", "canonical", "absolute", "outside", "traversal", "symlink", "directory"],
)
def test_consistency_uses_only_safe_stored_paths_or_legacy_identity(
    tmp_path: Path, stored: str
) -> None:
    root = tmp_path / "project"
    memory = root / ".cortex/memory-bank"
    _ = _write(root, ".cortex/memory-bank/legacy.md", b"legacy")
    canonical = _write(root, ".cortex/reviews/canonical.md", b"canonical")
    external = _write(tmp_path, "outside.md", b"outside")
    link = root / ".cortex/reviews/link.md"
    link.symlink_to(external)
    paths = {
        "canonical": ".cortex/reviews/canonical.md",
        "absolute": str(canonical),
        "outside": str(external),
        "traversal": "../outside.md",
        "symlink": ".cortex/reviews/link.md",
        "directory": ".cortex/reviews",
    }
    metadata: dict[str, object] = {} if stored == "legacy" else {"path": paths[stored]}
    data: dict[str, object] = {"files": {"legacy.md": metadata}}
    expected = [] if stored in {"legacy", "canonical", "absolute"} else ["legacy.md"]
    assert validate_index_consistency_from_data(data, memory, root) == expected


def _seed_typed_snapshot_history(root: Path) -> dict[str, object]:
    path = root / ".cortex/index.json"
    data = json.loads(path.read_bytes())
    snapshot = (root / ".cortex/history/report-0/9.md").read_bytes()
    history: dict[str, object] = {
        "version": 9,
        "timestamp": "2026-01-01",
        "content_hash": byte_hash(snapshot),
        "size_bytes": len(snapshot),
        "token_count": 5,
        "change_type": "created",
        "snapshot_path": ".cortex/history/report-0/9.md",
        "changed_sections": [],
        "change_description": "Pre-refactoring snapshot: retained",
    }
    data["files"]["reviews/report-0.md"]["version_history"] = [history]
    _ = path.write_bytes(json.dumps(data).encode())
    return history


async def test_snapshot_consumers_keep_typed_historical_versions(
    tmp_path: Path,
) -> None:
    mgrs, _, _ = _fixture(tmp_path)
    history = _seed_typed_snapshot_history(tmp_path)
    assert await file_has_snapshot("reviews/report-0.md", "retained", mgrs.index)
    versions = await get_version_history("reviews/report-0.md", mgrs.index)
    assert versions is not None
    assert len(versions) == 1
    assert versions[0].model_dump(mode="json") == history
    assert _index_files(tmp_path)["reviews/report-0.md"]["version_history"] == [history]
