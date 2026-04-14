"""Tests for session_start_impl success, workflow schema, and telemetry."""

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.context.effectiveness_operations import analyze_current_session
from cortex.tools.models import SessionStartResult
from cortex.tools.session.start_tools import session_start_impl
from tests.tools.session_start_fixtures import (
    assert_phase54_success_brief,
    build_minimal_session_managers_with_focus,
    managers_for_phase54_session_start,
    run_session_start_patched_mcp_healthy,
)


class TestSessionStartImpl:
    """Tests for session_start_impl."""

    @pytest.mark.asyncio
    async def test_session_start_impl_success(self, tmp_path: Path) -> None:
        """Test successful session start."""
        managers = await managers_for_phase54_session_start(tmp_path)
        result = await run_session_start_patched_mcp_healthy(tmp_path, managers)
        assert isinstance(result, SessionStartResult)
        assert_phase54_success_brief(result)
        assert isinstance(result.brief.memory_type_counts, dict)

    @pytest.mark.asyncio
    async def test_session_start_respects_session_yaml_workflow(
        self, tmp_path: Path
    ) -> None:
        """fast-path schema from .cortex/session.yaml omits review in brief phases."""
        import yaml

        from cortex.core.path_resolver import CortexResourceType, get_cortex_path

        cortex = get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR)
        cortex.mkdir(parents=True)
        _ = (cortex / "session.yaml").write_text(
            yaml.safe_dump({"workflow_schema": "fast-path"}), encoding="utf-8"
        )
        managers = await managers_for_phase54_session_start(tmp_path)
        result = await run_session_start_patched_mcp_healthy(tmp_path, managers)
        assert isinstance(result, SessionStartResult)
        joined = " ".join(result.brief.workflow_phases)
        assert "review" not in joined.lower()
        assert result.brief.workflow_schema == "fast-path"

    @pytest.mark.asyncio
    async def test_session_start_respects_session_yaml_compliance_workflow(
        self, tmp_path: Path
    ) -> None:
        """compliance schema lists security-review and review before commit."""
        import yaml

        from cortex.core.path_resolver import CortexResourceType, get_cortex_path

        cortex = get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR)
        cortex.mkdir(parents=True)
        _ = (cortex / "session.yaml").write_text(
            yaml.safe_dump({"workflow_schema": "compliance"}), encoding="utf-8"
        )
        managers = await managers_for_phase54_session_start(tmp_path)
        result = await run_session_start_patched_mcp_healthy(tmp_path, managers)
        assert isinstance(result, SessionStartResult)
        joined = " ".join(result.brief.workflow_phases)
        assert "security-review:" in joined
        assert joined.count("/cortex/review") == 2
        assert result.brief.workflow_schema == "compliance"

    @pytest.mark.asyncio
    async def test_session_start_data_science_omits_eda_when_condition_false(
        self, tmp_path: Path
    ) -> None:
        """data-science schema skips optional eda phase when eda_required is unset."""
        import yaml

        from cortex.core.path_resolver import CortexResourceType, get_cortex_path

        cortex = get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR)
        cortex.mkdir(parents=True)
        _ = (cortex / "session.yaml").write_text(
            yaml.safe_dump({"workflow_schema": "data-science"}), encoding="utf-8"
        )
        managers = await managers_for_phase54_session_start(tmp_path)
        result = await run_session_start_patched_mcp_healthy(tmp_path, managers)
        assert isinstance(result, SessionStartResult)
        joined = " ".join(result.brief.workflow_phases)
        assert "eda:" not in joined
        assert "plan:" in joined

    @pytest.mark.asyncio
    async def test_session_start_data_science_includes_eda_when_flag_set(
        self, tmp_path: Path
    ) -> None:
        """data-science schema includes eda when session.yaml sets eda_required."""
        import yaml

        from cortex.core.path_resolver import CortexResourceType, get_cortex_path

        cortex = get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR)
        cortex.mkdir(parents=True)
        _ = (cortex / "session.yaml").write_text(
            yaml.safe_dump(
                {"workflow_schema": "data-science", "eda_required": True},
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        managers = await managers_for_phase54_session_start(tmp_path)
        result = await run_session_start_patched_mcp_healthy(tmp_path, managers)
        assert isinstance(result, SessionStartResult)
        joined = " ".join(result.brief.workflow_phases)
        assert "eda:" in joined

    @pytest.mark.asyncio
    async def test_session_start_impl_seeds_context_telemetry_for_analysis(
        self, tmp_path: Path
    ) -> None:
        """Successful session_start writes one telemetry call to avoid no_data."""
        managers = await build_minimal_session_managers_with_focus(tmp_path, "Test.\n")
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "session_start_seed_1"
        try:
            with patch(
                "cortex.tools.session.health.get_mcp_health_status",
                new_callable=AsyncMock,
                return_value=(True, None),
            ):
                result = await session_start_impl(None, tmp_path, managers)  # type: ignore[arg-type]
            assert isinstance(result, SessionStartResult)
            assert result.status == "success"
            analysis = analyze_current_session(tmp_path)
            assert analysis.status == "success"
            current_raw = analysis.current_session
            assert current_raw is not None
            current = current_raw.model_dump(mode="python")
            assert current["calls_analyzed"] == 1
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    @pytest.mark.asyncio
    async def test_session_start_impl_does_not_duplicate_seeded_context_telemetry(
        self, tmp_path: Path
    ) -> None:
        """Repeated session_start in same session keeps a single seeded telemetry row."""
        managers = await build_minimal_session_managers_with_focus(tmp_path, "Test.\n")
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "session_start_seed_2"
        try:
            with patch(
                "cortex.tools.session.health.get_mcp_health_status",
                new_callable=AsyncMock,
                return_value=(True, None),
            ):
                _ = await session_start_impl(None, tmp_path, managers)  # type: ignore[arg-type]
                _ = await session_start_impl(None, tmp_path, managers)  # type: ignore[arg-type]
            analysis = analyze_current_session(tmp_path)
            assert analysis.status == "success"
            current_raw = analysis.current_session
            assert current_raw is not None
            current = current_raw.model_dump(mode="python")
            assert current["calls_analyzed"] == 1
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)
