"""
Tests for plan tool payload models and argument builders.

Covers PlanCreatePayload, PlanCompletePayload, PlanRegisterPayload,
to_plan_arguments, and build_*_arguments helpers.
"""

import json
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from cortex.tools.plans.plan import plan
from cortex.tools.plans.plan_payloads import (
    PlanCompletePayload,
    PlanCreatePayload,
    PlanOperation,
    PlanRegisterPayload,
    build_plan_complete_arguments,
    build_plan_create_arguments,
    build_plan_register_arguments,
    to_plan_arguments,
)


class TestPlanPayloadModels:
    """Validation and serialization of payload models."""

    def test_plan_complete_payload_required_fields(self) -> None:
        """PlanCompletePayload requires plan_title and summary."""
        p = PlanCompletePayload(
            plan_title="[MED-8] Foo",
            summary="Done.",
            completion_date=None,
            progress_entry=None,
            plan_file_name=None,
        )
        assert p.operation == PlanOperation.COMPLETE
        assert p.plan_title == "[MED-8] Foo"
        assert p.summary == "Done."
        assert p.completion_date is None
        assert p.progress_entry is None
        assert p.plan_file_name is None

    def test_plan_complete_payload_with_optionals(self) -> None:
        """PlanCompletePayload accepts optional fields."""
        p = PlanCompletePayload(
            plan_title="P",
            summary="S",
            completion_date="2026-03-12",
            progress_entry="Note",
            plan_file_name="p.md",
        )
        assert p.completion_date == "2026-03-12"
        assert p.progress_entry == "Note"
        assert p.plan_file_name == "p.md"

    def test_plan_register_payload_defaults(self) -> None:
        """PlanRegisterPayload has status and section defaults."""
        p = PlanRegisterPayload(
            plan_title="T", description="D", status="PENDING", section="pending"
        )
        assert p.operation == PlanOperation.REGISTER
        assert p.status == "PENDING"
        assert p.section == "pending"

    def test_plan_create_payload_required_fields(self) -> None:
        """PlanCreatePayload requires title and content."""
        p = PlanCreatePayload(
            title="Phase 1",
            content="# Plan\nBody",
            slug=None,
            include_archive=False,
            response_format="content",
        )
        assert p.operation == PlanOperation.CREATE
        assert p.title == "Phase 1"
        assert p.content == "# Plan\nBody"
        assert p.slug is None
        assert p.include_archive is False
        assert p.response_format == "content"


class TestToPlanArguments:
    """to_plan_arguments produces MCP-suitable dicts."""

    def test_complete_payload_exclude_none(self) -> None:
        """Optional None fields are omitted from the output."""
        p = PlanCompletePayload(
            plan_title="T",
            summary="S",
            completion_date=None,
            progress_entry=None,
            plan_file_name=None,
        )
        out = to_plan_arguments(p)
        assert out["operation"] == "complete"
        assert out["plan_title"] == "T"
        assert out["summary"] == "S"
        assert "completion_date" not in out
        assert "progress_entry" not in out
        assert "plan_file_name" not in out

    def test_complete_payload_include_optionals_when_set(self) -> None:
        """Optional fields are included when set."""
        p = PlanCompletePayload(
            plan_title="T",
            summary="S",
            completion_date="2026-03-12",
            progress_entry=None,
            plan_file_name="p.md",
        )
        out = to_plan_arguments(p)
        assert out["completion_date"] == "2026-03-12"
        assert out["plan_file_name"] == "p.md"

    def test_register_payload_serialization(self) -> None:
        """PlanRegisterPayload serializes to expected keys."""
        p = PlanRegisterPayload(
            plan_title="New plan",
            description="Short desc",
            status="IN_PROGRESS",
            section="blockers",
        )
        out = to_plan_arguments(p)
        assert out["operation"] == "register"
        assert out["plan_title"] == "New plan"
        assert out["description"] == "Short desc"
        assert out["status"] == "IN_PROGRESS"
        assert out["section"] == "blockers"

    def test_create_payload_serialization(self) -> None:
        """PlanCreatePayload serializes to expected keys."""
        p = PlanCreatePayload(
            title="Phase X",
            content="# Phase X\nBody",
            slug="phase-x",
            include_archive=False,
            response_format="content",
        )
        out = to_plan_arguments(p)
        assert out["operation"] == "create"
        assert out["title"] == "Phase X"
        assert out["content"] == "# Phase X\nBody"
        assert out["slug"] == "phase-x"


class TestBuildPlanArguments:
    """Builder helpers produce correct argument dicts."""

    def test_build_plan_complete_arguments_minimal(self) -> None:
        """build_plan_complete_arguments returns dict with operation, plan_title, summary."""
        d = build_plan_complete_arguments("My Plan", "Completed.")
        assert d["operation"] == "complete"
        assert d["plan_title"] == "My Plan"
        assert d["summary"] == "Completed."
        assert "completion_date" not in d

    def test_build_plan_complete_arguments_full(self) -> None:
        """build_plan_complete_arguments includes optionals when provided."""
        d = build_plan_complete_arguments(
            "P",
            "S",
            completion_date="2026-03-13",
            progress_entry="Done.",
            plan_file_name="p.md",
        )
        assert d["completion_date"] == "2026-03-13"
        assert d["progress_entry"] == "Done."
        assert d["plan_file_name"] == "p.md"

    def test_build_plan_register_arguments(self) -> None:
        """build_plan_register_arguments returns dict with defaults."""
        d = build_plan_register_arguments("Title", "Desc")
        assert d["operation"] == "register"
        assert d["plan_title"] == "Title"
        assert d["description"] == "Desc"
        assert d["status"] == "PENDING"
        assert d["section"] == "pending"

    def test_build_plan_create_arguments(self) -> None:
        """build_plan_create_arguments returns dict for create operation."""
        d = build_plan_create_arguments("# H1", "body", slug="slug")
        assert d["operation"] == "create"
        assert d["title"] == "# H1"
        assert d["content"] == "body"
        assert d["slug"] == "slug"


class TestPlanPayloadGuardrails:
    """Guardrail tests: helpers and payloads fail early on missing/invalid required fields."""

    def test_plan_complete_payload_empty_plan_title_raises(self) -> None:
        """PlanCompletePayload with empty plan_title raises ValidationError."""
        with pytest.raises(ValidationError):
            _ = PlanCompletePayload(
                plan_title="",
                summary="Done",
                completion_date=None,
                progress_entry=None,
                plan_file_name=None,
            )

    def test_plan_complete_payload_empty_summary_raises(self) -> None:
        """PlanCompletePayload with empty summary raises ValidationError."""
        with pytest.raises(ValidationError):
            _ = PlanCompletePayload(
                plan_title="[MED-8] Foo",
                summary="",
                completion_date=None,
                progress_entry=None,
                plan_file_name=None,
            )

    def test_plan_register_payload_empty_plan_title_raises(self) -> None:
        """PlanRegisterPayload with empty plan_title raises ValidationError."""
        with pytest.raises(ValidationError):
            _ = PlanRegisterPayload(
                plan_title="",
                description="Short desc",
                status="PENDING",
                section="pending",
            )

    def test_plan_register_payload_empty_description_raises(self) -> None:
        """PlanRegisterPayload with empty description raises ValidationError."""
        with pytest.raises(ValidationError):
            _ = PlanRegisterPayload(
                plan_title="Title",
                description="",
                status="PENDING",
                section="pending",
            )

    def test_plan_create_payload_empty_title_raises(self) -> None:
        """PlanCreatePayload with empty title raises ValidationError."""
        with pytest.raises(ValidationError):
            _ = PlanCreatePayload(
                title="",
                content="Body",
                slug=None,
                include_archive=False,
                response_format="content",
            )

    def test_plan_create_payload_empty_content_raises(self) -> None:
        """PlanCreatePayload with empty content raises ValidationError."""
        with pytest.raises(ValidationError):
            _ = PlanCreatePayload(
                title="Phase",
                content="",
                slug=None,
                include_archive=False,
                response_format="content",
            )

    def test_build_plan_complete_arguments_empty_plan_title_raises(self) -> None:
        """build_plan_complete_arguments with empty plan_title fails early."""
        with pytest.raises(ValidationError):
            _ = build_plan_complete_arguments("", "Summary")

    def test_build_plan_complete_arguments_empty_summary_raises(self) -> None:
        """build_plan_complete_arguments with empty summary fails early."""
        with pytest.raises(ValidationError):
            _ = build_plan_complete_arguments("My Plan", "")

    def test_build_plan_register_arguments_empty_plan_title_raises(self) -> None:
        """build_plan_register_arguments with empty plan_title fails early."""
        with pytest.raises(ValidationError):
            _ = build_plan_register_arguments("", "Description")

    def test_build_plan_register_arguments_empty_description_raises(self) -> None:
        """build_plan_register_arguments with empty description fails early."""
        with pytest.raises(ValidationError):
            _ = build_plan_register_arguments("Title", "")

    def test_build_plan_create_arguments_empty_title_raises(self) -> None:
        """build_plan_create_arguments with empty title fails early."""
        with pytest.raises(ValidationError):
            _ = build_plan_create_arguments("", "body")

    def test_build_plan_create_arguments_empty_content_raises(self) -> None:
        """build_plan_create_arguments with empty content fails early."""
        with pytest.raises(ValidationError):
            _ = build_plan_create_arguments("Title", "")


@pytest.mark.timeout(15)
class TestPlanToolAcceptsBuiltPayloads:
    """Built payloads are accepted by the plan tool (past validation).

    Uses a temp directory as project root so tests don't pollute the real
    .cortex/plans/ or roadmap.md.
    """

    @pytest.fixture(autouse=True)
    def _isolate_project_root(self) -> Generator[None]:
        """Redirect resolve_project_root_async to a temp dir."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Create the directory structure plan operations expect
            (tmp_path / ".cortex" / "plans").mkdir(parents=True)
            (tmp_path / ".cortex" / "memory-bank").mkdir(parents=True)
            # Provide a minimal roadmap so register doesn't fail on missing file
            _ = (tmp_path / ".cortex" / "memory-bank" / "roadmap.md").write_text(
                "# Roadmap\n\n## Pending plans (from .cortex/plans)\n\n### Features & Enhancements\n"
            )
            mock_root = AsyncMock(return_value=tmp_path)
            # Patch at every import site used by plan operations
            targets = [
                "cortex.tools.plans.crud.resolve_project_root_async",
                "cortex.tools.plans.register.resolve_project_root_async",
                "cortex.tools.plans.completion.resolve_project_root_async",
                "cortex.tools.plans.entries.resolve_project_root_async",
                "cortex.tools.plans.corruption.resolve_project_root_async",
            ]
            patches = [patch(t, mock_root) for t in targets]
            for p in patches:
                _ = p.start()
            yield
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_complete_built_payload_passes_validation(self) -> None:
        """plan(**build_plan_complete_arguments(...)) passes required-field validation."""
        kwargs = build_plan_complete_arguments("[Test] Plan", "Summary")
        result_str = await plan(**kwargs)
        result = json.loads(result_str)
        # Should not be the "plan_title and summary are required" error.
        message = (result.get("message") or "").lower()
        assert "plan_title and summary are required" not in message
        # May still be error from implementation (e.g. roadmap entry not found).
        assert "status" in result

    @pytest.mark.asyncio
    async def test_register_built_payload_passes_validation(self) -> None:
        """plan(**build_plan_register_arguments(...)) passes required-field validation."""
        kwargs = build_plan_register_arguments("Test Plan", "Description")
        result_str = await plan(**kwargs)
        result = json.loads(result_str)
        message = (result.get("message") or "").lower()
        assert "plan_title and description are required" not in message
        assert "status" in result

    @pytest.mark.asyncio
    async def test_create_built_payload_passes_validation(self) -> None:
        """plan(**build_plan_create_arguments(...)) passes required-field validation."""
        kwargs = build_plan_create_arguments("Test Plan", "# Body\nContent here.")
        result_str = await plan(**kwargs)
        result = json.loads(result_str)
        message = (result.get("message") or "").lower()
        assert "title and content are required" not in message
        assert "status" in result
