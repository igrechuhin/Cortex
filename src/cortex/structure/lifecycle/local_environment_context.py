from __future__ import annotations

import json
import platform
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.pydantic_extra import EXTRA_FORBID

LOCAL_ENV_CONTEXT_FILENAME = "local-environment-context.json"


class ArtifactMeta(BaseModel):
    model_config = ConfigDict(extra=EXTRA_FORBID)
    name: str
    purpose: str
    local_only: bool
    git_untracked: bool
    canonical_path: str


class MachineBinding(BaseModel):
    model_config = ConfigDict(extra=EXTRA_FORBID)
    host_fingerprint: str
    hostname: str


class HostEnvironment(BaseModel):
    model_config = ConfigDict(extra=EXTRA_FORBID)
    os: str
    os_version: str
    architecture: str
    python_version: str


class ToolchainInfo(BaseModel):
    model_config = ConfigDict(extra=EXTRA_FORBID)
    python_implementation: str
    python_compiler: str


class DeployTarget(BaseModel):
    model_config = ConfigDict(extra=EXTRA_FORBID)
    architecture: str
    notes: str
    requires_user_confirmation: list[str] = Field(default_factory=list)


class LocalEnvironmentPayload(BaseModel):
    model_config = ConfigDict(extra=EXTRA_FORBID)
    schema_version: str
    artifact: ArtifactMeta
    machine_binding: MachineBinding
    host_environment: HostEnvironment
    toolchain: ToolchainInfo
    deploy_target: DeployTarget
    last_refreshed_utc: str


@dataclass(frozen=True)
class LocalEnvironmentContextResult:
    created: bool
    updated: bool
    mismatch_warning: str | None = None
    parse_warning: str | None = None


def ensure_local_environment_context(
    project_root: Path,
) -> LocalEnvironmentContextResult:
    artifact_path = _artifact_path(project_root)
    current = _build_current_environment_payload(project_root)
    if not artifact_path.is_file():
        _write_payload(artifact_path, current)
        return LocalEnvironmentContextResult(created=True, updated=False)
    existing, parse_warning = _load_existing_payload(artifact_path)
    if existing is None:
        _write_payload(artifact_path, current)
        return LocalEnvironmentContextResult(
            created=False, updated=True, parse_warning=parse_warning
        )
    mismatch_warning = _binding_mismatch_warning(existing, current)
    merged = _merge_payload(existing, current, project_root)
    if _payload_changed(existing, merged):
        _write_payload(artifact_path, merged)
        return LocalEnvironmentContextResult(
            created=False, updated=True, mismatch_warning=mismatch_warning
        )
    return LocalEnvironmentContextResult(
        created=False, updated=False, mismatch_warning=mismatch_warning
    )


def _artifact_path(project_root: Path) -> Path:
    memory_bank_dir = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    memory_bank_dir.mkdir(parents=True, exist_ok=True)
    return memory_bank_dir / LOCAL_ENV_CONTEXT_FILENAME


def _load_existing_payload(
    path: Path,
) -> tuple[LocalEnvironmentPayload | None, str | None]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return LocalEnvironmentPayload.model_validate(raw), None
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        return None, f"local environment artifact was invalid and regenerated: {exc}"


def _binding_mismatch_warning(
    existing: LocalEnvironmentPayload, current: LocalEnvironmentPayload
) -> str | None:
    if (
        existing.machine_binding.host_fingerprint
        == current.machine_binding.host_fingerprint
    ):
        return None
    return (
        "local environment binding mismatch detected; workspace may have been "
        "copied from another machine. Run /cortex/rebind_local_environment_context "
        "to regenerate the artifact for this host, then rerun your previous command."
    )


def _merge_payload(
    existing: LocalEnvironmentPayload,
    current: LocalEnvironmentPayload,
    project_root: Path,
) -> LocalEnvironmentPayload:
    deploy_target = existing.deploy_target
    if _should_replace_legacy_generic_deploy_target(
        existing.deploy_target, project_root
    ):
        deploy_target = current.deploy_target
    return LocalEnvironmentPayload(
        schema_version=current.schema_version,
        artifact=current.artifact,
        machine_binding=current.machine_binding,
        host_environment=current.host_environment,
        toolchain=current.toolchain,
        deploy_target=deploy_target,
        last_refreshed_utc=current.last_refreshed_utc,
    )


def _payload_changed(
    existing: LocalEnvironmentPayload, updated: LocalEnvironmentPayload
) -> bool:
    existing_dump = existing.model_dump(mode="json")
    updated_dump = updated.model_dump(mode="json")
    return updated_dump != existing_dump


def _write_payload(path: Path, payload: LocalEnvironmentPayload) -> None:
    payload_json = payload.model_dump(mode="json")
    _ = path.write_text(
        json.dumps(payload_json, indent=2, sort_keys=True) + "\n", "utf-8"
    )


def _build_current_environment_payload(project_root: Path) -> LocalEnvironmentPayload:
    architecture = platform.machine().lower()
    system_name = platform.system()
    host_name = socket.gethostname()
    host_fingerprint = f"{host_name}:{system_name}:{architecture}"
    return LocalEnvironmentPayload(
        schema_version="1.0",
        artifact=_build_artifact_meta(),
        machine_binding=MachineBinding(
            host_fingerprint=host_fingerprint, hostname=host_name
        ),
        host_environment=_build_host_environment(system_name, architecture),
        toolchain=_build_toolchain_info(),
        deploy_target=_build_default_deploy_target(project_root),
        last_refreshed_utc=datetime.now(UTC).isoformat(),
    )


def _build_artifact_meta() -> ArtifactMeta:
    return ArtifactMeta(
        name=LOCAL_ENV_CONTEXT_FILENAME,
        purpose="Machine-local context for architecture-aware Cortex workflows.",
        local_only=True,
        git_untracked=True,
        canonical_path=f".cortex/memory-bank/{LOCAL_ENV_CONTEXT_FILENAME}",
    )


def _build_host_environment(system_name: str, architecture: str) -> HostEnvironment:
    return HostEnvironment(
        os=system_name,
        os_version=platform.version(),
        architecture=architecture,
        python_version=platform.python_version(),
    )


def _build_toolchain_info() -> ToolchainInfo:
    return ToolchainInfo(
        python_implementation=platform.python_implementation(),
        python_compiler=platform.python_compiler(),
    )


def _build_default_deploy_target(project_root: Path) -> DeployTarget:
    _ = project_root
    return DeployTarget(
        architecture="unknown",
        notes=(
            "Deploy target is project-specific. Derive architecture from project "
            "context and update this field before using it in architecture-aware flows."
        ),
        requires_user_confirmation=["architecture"],
    )


def _should_replace_legacy_generic_deploy_target(
    deploy_target: DeployTarget, project_root: Path
) -> bool:
    _ = project_root
    return (
        deploy_target.architecture == "x86_64"
        and deploy_target.notes
        == "Default deploy target is Intel/x86_64. Update this field if your target differs."
        and deploy_target.requires_user_confirmation == ["architecture"]
    )
