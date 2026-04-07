"""Tests for write_artifact tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.tools.artifacts.write_artifact import ArtifactType, write_artifact
from cortex.tools.skill_pack.operations import skill_pack


def _valid_skill_json(name: str) -> str:
    return json.dumps(
        {
            "name": name,
            "description": "Skill test pack",
            "tools": ["session"],
            "when_to_use": "When testing tool writes",
            "workflow_sequences": ["session -> run_quality_gate"],
            "example_invocations": ["session(operation='start')"],
            "troubleshooting_tips": ["Check JSON fields"],
            "keywords": ["testing"],
        }
    )


def _valid_rule_mdc() -> str:
    return (
        "---\n" "description: Test rule\n" "alwaysApply: false\n" "---\n\n" "Rule body."
    )


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_write_skill_creates_valid_json_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cortex.tools.artifacts import write_artifact as module

    skills_dir = tmp_path / "skills"
    monkeypatch.setattr(module, "_get_skills_dir", lambda: skills_dir)

    async def _fake_root(_: object) -> Path:
        return tmp_path

    monkeypatch.setattr(module, "get_or_resolve_project_root", _fake_root)

    result = await write_artifact(
        artifact_type=ArtifactType.SKILL,
        name="new-skill",
        content=_valid_skill_json("new-skill"),
    )

    data = json.loads(result)
    assert data["status"] == "success"
    written = skills_dir / "new-skill.json"
    assert written.exists()
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["name"] == "new-skill"


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_write_skill_rejects_invalid_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cortex.tools.artifacts import write_artifact as module

    monkeypatch.setattr(module, "_get_skills_dir", lambda: tmp_path / "skills")

    async def _fake_root(_: object) -> Path:
        return tmp_path

    monkeypatch.setattr(module, "get_or_resolve_project_root", _fake_root)

    result = await write_artifact(
        artifact_type=ArtifactType.SKILL,
        name="bad-skill",
        content="{not-json}",
    )

    data = json.loads(result)
    assert data["status"] == "error"


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_write_skill_rejects_missing_required_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cortex.tools.artifacts import write_artifact as module

    monkeypatch.setattr(module, "_get_skills_dir", lambda: tmp_path / "skills")

    async def _fake_root(_: object) -> Path:
        return tmp_path

    monkeypatch.setattr(module, "get_or_resolve_project_root", _fake_root)

    incomplete_skill = json.dumps({"description": "missing name/tools"})
    result = await write_artifact(
        artifact_type=ArtifactType.SKILL,
        name="incomplete-skill",
        content=incomplete_skill,
    )

    data = json.loads(result)
    assert data["status"] == "error"


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_write_rule_creates_mdc_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cortex.tools.artifacts import write_artifact as module

    async def _fake_root(_: object) -> Path:
        return tmp_path

    monkeypatch.setattr(module, "get_or_resolve_project_root", _fake_root)

    result = await write_artifact(
        artifact_type=ArtifactType.RULE,
        name="general/new-rule.mdc",
        content=_valid_rule_mdc(),
    )

    data = json.loads(result)
    assert data["status"] == "success"
    written = tmp_path / ".cortex" / "synapse" / "rules" / "general" / "new-rule.mdc"
    assert written.exists()
    assert written.read_text(encoding="utf-8") == _valid_rule_mdc()


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_write_rule_rejects_missing_frontmatter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cortex.tools.artifacts import write_artifact as module

    async def _fake_root(_: object) -> Path:
        return tmp_path

    monkeypatch.setattr(module, "get_or_resolve_project_root", _fake_root)

    result = await write_artifact(
        artifact_type=ArtifactType.RULE,
        name="general/bad-rule.mdc",
        content="no frontmatter",
    )

    data = json.loads(result)
    assert data["status"] == "error"


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_write_rule_rejects_frontmatter_without_description(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cortex.tools.artifacts import write_artifact as module

    async def _fake_root(_: object) -> Path:
        return tmp_path

    monkeypatch.setattr(module, "get_or_resolve_project_root", _fake_root)

    content = "---\nalwaysApply: false\n---\n\nRule"
    result = await write_artifact(
        artifact_type=ArtifactType.RULE,
        name="general/missing-description.mdc",
        content=content,
    )

    data = json.loads(result)
    assert data["status"] == "error"


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_write_artifact_rejects_path_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cortex.tools.artifacts import write_artifact as module

    monkeypatch.setattr(module, "_get_skills_dir", lambda: tmp_path / "skills")

    async def _fake_root(_: object) -> Path:
        return tmp_path

    monkeypatch.setattr(module, "get_or_resolve_project_root", _fake_root)

    result = await write_artifact(
        artifact_type=ArtifactType.RULE,
        name="../../etc/passwd.mdc",
        content=_valid_rule_mdc(),
    )

    data = json.loads(result)
    assert data["status"] == "error"


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_write_artifact_rejects_absolute_path_in_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cortex.tools.artifacts import write_artifact as module

    monkeypatch.setattr(module, "_get_skills_dir", lambda: tmp_path / "skills")

    async def _fake_root(_: object) -> Path:
        return tmp_path

    monkeypatch.setattr(module, "get_or_resolve_project_root", _fake_root)

    result = await write_artifact(
        artifact_type=ArtifactType.RULE,
        name="/tmp/evil.mdc",
        content=_valid_rule_mdc(),
    )

    data = json.loads(result)
    assert data["status"] == "error"


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_write_skill_is_discoverable_after_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cortex.tools.artifacts import write_artifact as module
    from cortex.tools.skill_pack import operations as skill_pack_module

    skills_dir = tmp_path / "skills"
    monkeypatch.setattr(module, "_get_skills_dir", lambda: skills_dir)
    monkeypatch.setattr(skill_pack_module, "_skills_dir", skills_dir)

    async def _fake_root(_: object) -> Path:
        return tmp_path

    monkeypatch.setattr(module, "get_or_resolve_project_root", _fake_root)

    result = await write_artifact(
        artifact_type=ArtifactType.SKILL,
        name="discoverable-skill",
        content=_valid_skill_json("discoverable-skill"),
    )
    write_data = json.loads(result)
    assert write_data["status"] == "success"

    load_result = await skill_pack(operation="load", pack_name="discoverable-skill")
    load_data = json.loads(load_result)
    assert load_data["status"] == "success"
    assert load_data["pack"]["name"] == "discoverable-skill"


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_write_rule_creates_parent_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cortex.tools.artifacts import write_artifact as module

    async def _fake_root(_: object) -> Path:
        return tmp_path

    monkeypatch.setattr(module, "get_or_resolve_project_root", _fake_root)

    result = await write_artifact(
        artifact_type=ArtifactType.RULE,
        name="python/nested/new-rule.mdc",
        content=_valid_rule_mdc(),
    )

    data = json.loads(result)
    assert data["status"] == "success"
    expected = (
        tmp_path
        / ".cortex"
        / "synapse"
        / "rules"
        / "python"
        / "nested"
        / "new-rule.mdc"
    )
    assert expected.exists()
