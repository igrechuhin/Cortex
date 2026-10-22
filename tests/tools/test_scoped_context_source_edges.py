"""Source selection edge cases and unchanged layer contracts."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from cortex.tools.context.layers import ContextLayer, LayerResult
from cortex.tools.context.scoped_context import build_scoped_context_packet
from cortex.tools.context.scoped_evidence_state import ScopedEvidenceState
from cortex.tools.context.scoped_readiness import ScopedReadiness
from cortex.tools.context.scoped_source_state import ScopedSourceState
from cortex.tools.context.scoped_task_state import ScopedTaskState
from cortex.tools.context.source_revision import SourceRevision
from cortex.tools.optimization import handlers
from cortex.tools.optimization.scoped_resource import (
    parse_context_layers,
    render_context_layer,
)
from tests.tools.scoped_revision_test_support import (
    ScopedResourceHarness,
    manifest,
    task_state,
    write_plan,
    write_source,
)


@pytest.mark.asyncio
async def test_done_dependency_content_only_change_invalidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    harness = ScopedResourceHarness(tmp_path, monkeypatch)
    _ = write_plan(tmp_path, dependencies=["dependency"])
    _ = write_plan(tmp_path, "dependency", "DONE", goal="Original dependency details.")
    first = await harness.read()
    # Act
    path = write_plan(
        tmp_path, "dependency", "DONE", goal="Changed dependency details."
    )
    second = await harness.read()
    # Assert
    assert harness.calls == 2
    assert (
        task_state(first).readiness
        is task_state(second).readiness
        is ScopedReadiness.READY
    )
    assert (
        manifest(second)["plan:dependency"].revision
        == sha256(path.read_bytes()).hexdigest()
    )
    assert (
        manifest(first)["plan:dependency"].revision
        != manifest(second)["plan:dependency"].revision
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw", "issue"),
    [
        ("[]", "invalid_rules_payload"),
        ('{"status": "error"}', "missing_rules"),
        ('{"rules": [{"content": ""}]}', "invalid_rule"),
        (
            '{"rules": [{"content": "Rule without source metadata"}]}',
            "missing_rule_provenance",
        ),
        (
            '{"rules": [{"file": "missing.mdc", "content": "Missing original"}]}',
            "missing_rule_source",
        ),
        (
            '{"rules": [{"file": "../../escape.mdc", "content": "Outside root"}]}',
            "missing_rule_provenance",
        ),
        (
            '{"rules": [{"source": "local", "file": "a.mdc", "content": "No local folder"}]}',
            "missing_rule_provenance",
        ),
    ],
)
async def test_invalid_or_missing_rule_evidence_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw: str, issue: str
) -> None:
    # Arrange
    harness = ScopedResourceHarness(tmp_path, monkeypatch)

    async def selected_rules() -> str:
        return raw

    monkeypatch.setattr(handlers, "get_relevant_rules", selected_rules)
    # Act
    payload = await harness.read()
    # Assert
    assert payload["status"] == "success"
    assert any(item.code == issue for item in task_state(payload).issues)


@pytest.mark.asyncio
async def test_selected_shared_rule_retains_category_and_original_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    harness = ScopedResourceHarness(tmp_path, monkeypatch)
    original = write_source(
        tmp_path,
        ".cortex/synapse/rules/general/selected.mdc",
        "## Universal\nShared rule.\n",
    )

    async def shared_rules() -> str:
        return json.dumps(
            {
                "rules": [
                    {
                        "source": "shared",
                        "category": "general",
                        "file": "selected.mdc",
                        "content": original.read_text(encoding="utf-8"),
                    }
                ]
            }
        )

    monkeypatch.setattr(handlers, "get_relevant_rules", shared_rules)
    # Act
    payload = await harness.read()
    # Assert
    source = manifest(payload)["source:rule:shared:general:selected.mdc"]
    assert source.reference == ".cortex/synapse/rules/general/selected.mdc"
    assert source.revision == sha256(original.read_bytes()).hexdigest()
    assert not any(
        item.code == "missing_rule_source" for item in task_state(payload).issues
    )


@pytest.mark.asyncio
async def test_unreadable_selected_plan_is_evidenced_not_silently_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    path = write_plan(tmp_path)
    original_read = Path.read_bytes

    def fail_selected(selected: Path) -> bytes:
        if selected == path:
            raise PermissionError("selected source unavailable")
        return original_read(selected)

    monkeypatch.setattr(Path, "read_bytes", fail_selected)
    # Act
    packet = build_scoped_context_packet(
        project_root=tmp_path, scope="plan:selected", rules_payload=""
    )
    # Assert
    assert packet is not None
    assert packet["freshness"] == "warnings"
    assert "error" in packet
    assert "unreadable" in str(packet["revision_manifest"])


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, ["l0", "l1"]),
        ([], ["l0", "l1"]),
        (["l3", "l3", "invalid"], ["l0", "l1", "l3"]),
        ("L2, l1", ["l0", "l2", "l1"]),
        ("invalid", ["l0", "l1"]),
    ],
)
def test_existing_layer_parser_semantics_are_preserved(
    raw: object, expected: list[str]
) -> None:
    # Arrange / Act
    layers = parse_context_layers(raw)
    # Assert
    assert [layer.value for layer in layers] == expected


@pytest.mark.parametrize("layer", list(ContextLayer))
def test_existing_layer_renderer_labels_are_preserved(layer: ContextLayer) -> None:
    # Arrange
    result = LayerResult(
        layer=layer, tokens_estimate=1, content="Selected layer", sources=[]
    )
    # Act
    rendered = render_context_layer(result)
    # Assert
    assert rendered.startswith(f"### {layer.value.upper()} ")
    assert rendered.endswith("Selected layer")
    assert render_context_layer(result.model_copy(update={"content": " "})) == ""


@pytest.mark.asyncio
async def test_append_only_rule_prohibition_reports_stale_cached_delivery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: simulate the real rules resource's independent cached payload.
    harness = ScopedResourceHarness(tmp_path, monkeypatch)
    cached_payload = await harness.read_rules()
    original = harness.rule.read_text(encoding="utf-8")

    async def cached_rules() -> str:
        return cached_payload

    monkeypatch.setattr(handlers, "get_relevant_rules", cached_rules)
    first = await harness.read()
    # Act: old delivered text remains an exact prefix of the changed source.
    _ = harness.rule.write_text(
        original + "\nNever deploy without approval.\n", encoding="utf-8"
    )
    second = await harness.read()
    # Assert
    assert harness.calls == 2
    assert not any(
        item.code == "stale_rule_payload" for item in task_state(first).issues
    )
    assert any(item.code == "stale_rule_payload" for item in task_state(second).issues)
    key = "source:rule:local:general:selected.mdc"
    assert (
        manifest(second)[key].revision == sha256(harness.rule.read_bytes()).hexdigest()
    )
    assert manifest(first)[key].revision != manifest(second)[key].revision


@pytest.mark.asyncio
async def test_rule_comparison_matches_loader_universal_newline_normalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    harness = ScopedResourceHarness(tmp_path, monkeypatch)
    original = b"## Universal\r\nKeep complete selected rule.\r"
    _ = harness.rule.write_bytes(original)
    # Act: the actual fixture loader uses read_text, like the canonical rule indexer.
    payload = await harness.read()
    # Assert
    assert not any(
        item.code == "stale_rule_payload" for item in task_state(payload).issues
    )
    assert (
        manifest(payload)["source:rule:local:general:selected.mdc"].revision
        == sha256(original).hexdigest()
    )


def test_internal_state_enums_preserve_existing_wire_labels() -> None:
    # Arrange
    source = SourceRevision(
        identity="selected",
        kind="plan",
        reference="plan:selected",
        provenance="canonical",
    )
    task = ScopedTaskState()
    # Act
    task.evidence(
        "status", "conflict", ["plan:selected"], ScopedEvidenceState.CONFLICTING
    )
    restored_source = SourceRevision.model_validate_json(source.model_dump_json())
    restored_task = ScopedTaskState.model_validate_json(task.model_dump_json())
    # Assert: internal enums remain typed, while serialized API values stay unchanged.
    assert restored_source.state is ScopedSourceState.PRESENT
    assert restored_task.readiness is ScopedReadiness.UNKNOWN
    assert restored_task.status.state is ScopedEvidenceState.CONFLICTING
    assert restored_source.model_dump(mode="json")["state"] == "present"
    assert restored_task.model_dump(mode="json")["readiness"] == "unknown"
