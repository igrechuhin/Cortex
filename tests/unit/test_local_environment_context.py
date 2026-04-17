"""Unit tests for local environment context lifecycle behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.structure.lifecycle.local_environment_context import (
    LOCAL_ENV_CONTEXT_FILENAME,
    LocalEnvironmentPayload,
    ensure_local_environment_context,
)

_BASE_ARTIFACT = {
    "name": LOCAL_ENV_CONTEXT_FILENAME,
    "purpose": "Machine-local context for architecture-aware Cortex workflows.",
    "local_only": True,
    "git_untracked": True,
    "canonical_path": f".cortex/memory-bank/{LOCAL_ENV_CONTEXT_FILENAME}",
}
_BASE_HOST = {
    "os": "Darwin",
    "os_version": "os-v1",
    "architecture": "arm64",
    "python_version": "3.13.2",
}
_BASE_TOOLCHAIN = {
    "python_implementation": "CPython",
    "python_compiler": "Clang",
}
_BASE_DEPLOY = {
    "architecture": "unknown",
    "notes": "project-specific deploy target",
    "requires_user_confirmation": ["architecture"],
}


def _build_payload(overrides: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "artifact": dict(_BASE_ARTIFACT),
        "machine_binding": {
            "host_fingerprint": "host-a:Darwin:arm64",
            "hostname": "host-a",
        },
        "host_environment": dict(_BASE_HOST),
        "toolchain": dict(_BASE_TOOLCHAIN),
        "deploy_target": dict(_BASE_DEPLOY),
        "last_refreshed_utc": "2026-04-17T00:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def _payload_dict(
    *,
    host_fingerprint: str = "host-a:Darwin:arm64",
    hostname: str = "host-a",
    architecture: str = "arm64",
    os_version: str = "os-v1",
    deploy_architecture: str = "unknown",
    deploy_notes: str = "project-specific deploy target",
    refreshed_utc: str = "2026-04-17T00:00:00+00:00",
) -> dict[str, object]:
    return _build_payload(
        {
            "machine_binding": {
                "host_fingerprint": host_fingerprint,
                "hostname": hostname,
            },
            "host_environment": {
                **_BASE_HOST,
                "os_version": os_version,
                "architecture": architecture,
            },
            "deploy_target": {
                **_BASE_DEPLOY,
                "architecture": deploy_architecture,
                "notes": deploy_notes,
            },
            "last_refreshed_utc": refreshed_utc,
        }
    )


def _patch_current_payload(
    monkeypatch: pytest.MonkeyPatch, payload: LocalEnvironmentPayload
) -> None:
    def _replacement(project_root: Path) -> LocalEnvironmentPayload:
        _ = project_root
        return payload

    monkeypatch.setattr(
        "cortex.structure.lifecycle.local_environment_context._build_current_environment_payload",
        _replacement,
    )


def _write_payload(path: Path, payload: dict[str, object]) -> None:
    _ = path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _artifact_path(project_root: Path) -> Path:
    return project_root / ".cortex" / "memory-bank" / LOCAL_ENV_CONTEXT_FILENAME


def _assert_deploy_target(path: Path, *, architecture: str, notes: str) -> None:
    content = json.loads(path.read_text(encoding="utf-8"))
    assert content["deploy_target"]["architecture"] == architecture
    assert content["deploy_target"]["notes"] == notes


def _assert_host_os_version(path: Path, expected: str) -> None:
    content = json.loads(path.read_text(encoding="utf-8"))
    assert content["host_environment"]["os_version"] == expected


def test_invalid_json_is_regenerated(tmp_path: Path) -> None:
    # Arrange
    artifact = _artifact_path(tmp_path)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    _ = artifact.write_text("{invalid-json", encoding="utf-8")

    # Act
    result = ensure_local_environment_context(tmp_path)

    # Assert
    assert result.created is False
    assert result.updated is True
    assert result.parse_warning is not None
    parsed = json.loads(artifact.read_text(encoding="utf-8"))
    assert parsed["schema_version"] == "1.0"
    assert parsed["artifact"]["name"] == LOCAL_ENV_CONTEXT_FILENAME
    assert parsed["deploy_target"]["architecture"] == "unknown"


def test_deploy_target_preserved_when_merging_existing_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    artifact = _artifact_path(tmp_path)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    _write_payload(
        artifact,
        _payload_dict(
            deploy_architecture="aarch64",
            deploy_notes="custom deploy target notes",
            refreshed_utc="2026-04-17T00:00:00+00:00",
        ),
    )
    current_payload = LocalEnvironmentPayload.model_validate(
        _payload_dict(
            host_fingerprint="host-b:Darwin:arm64",
            hostname="host-b",
            os_version="os-v2",
            deploy_architecture="unknown",
            deploy_notes="new default that should not overwrite custom value",
            refreshed_utc="2026-04-17T00:01:00+00:00",
        )
    )
    _patch_current_payload(monkeypatch, current_payload)

    # Act
    result = ensure_local_environment_context(tmp_path)

    # Assert
    assert result.updated is True
    _assert_deploy_target(
        artifact, architecture="aarch64", notes="custom deploy target notes"
    )


def test_idempotent_when_payload_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    payload = LocalEnvironmentPayload.model_validate(_payload_dict())
    _patch_current_payload(monkeypatch, payload)
    first = ensure_local_environment_context(tmp_path)
    artifact = _artifact_path(tmp_path)
    original_content = artifact.read_text(encoding="utf-8")

    # Act
    second = ensure_local_environment_context(tmp_path)

    # Assert
    assert first.created is True
    assert first.updated is False
    assert second.created is False
    assert second.updated is False
    assert artifact.read_text(encoding="utf-8") == original_content


def test_payload_change_boundary_deploy_target_only_does_not_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    artifact = _artifact_path(tmp_path)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    _write_payload(
        artifact,
        _payload_dict(
            deploy_architecture="unknown",
            deploy_notes="operator override",
            refreshed_utc="2026-04-17T00:00:00+00:00",
        ),
    )
    deploy_only_changed = LocalEnvironmentPayload.model_validate(
        _payload_dict(
            deploy_architecture="arm64",
            deploy_notes="auto-detected default changed",
            refreshed_utc="2026-04-17T00:00:00+00:00",
        )
    )
    _patch_current_payload(monkeypatch, deploy_only_changed)

    # Act
    result = ensure_local_environment_context(tmp_path)

    # Assert
    assert result.updated is False
    _assert_deploy_target(artifact, architecture="unknown", notes="operator override")


def test_legacy_generic_x86_default_is_migrated_for_non_tradewing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    artifact = _artifact_path(tmp_path)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    _write_payload(
        artifact,
        _payload_dict(
            deploy_architecture="x86_64",
            deploy_notes=(
                "Default deploy target is Intel/x86_64. Update this field if your target differs."
            ),
        ),
    )
    non_tradewing_payload = LocalEnvironmentPayload.model_validate(_payload_dict())
    _patch_current_payload(monkeypatch, non_tradewing_payload)

    # Act
    result = ensure_local_environment_context(tmp_path)

    # Assert
    assert result.updated is True
    _assert_deploy_target(
        artifact,
        architecture="unknown",
        notes="project-specific deploy target",
    )


def test_payload_change_boundary_non_deploy_change_updates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    artifact = _artifact_path(tmp_path)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    _write_payload(
        artifact,
        _payload_dict(
            os_version="os-v1",
            refreshed_utc="2026-04-17T00:00:00+00:00",
        ),
    )
    non_deploy_changed = LocalEnvironmentPayload.model_validate(
        _payload_dict(
            os_version="os-v2",
            refreshed_utc="2026-04-17T00:02:00+00:00",
        )
    )
    _patch_current_payload(monkeypatch, non_deploy_changed)

    # Act
    result = ensure_local_environment_context(tmp_path)

    # Assert
    assert result.updated is True
    _assert_host_os_version(artifact, "os-v2")
