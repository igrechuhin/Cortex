"""Tests for AgentRole detection and profiles (Phase 58)."""

from cortex.optimization.agent_roles import (
    ROLE_PROFILES,
    AgentRole,
    detect_agent_role,
    get_role_profile,
    normalize_role_name,
)


class TestAgentRoleDetection:
    """Tests for keyword-based role detection."""

    def test_detect_debugging_role_from_fix_keywords(self) -> None:
        role = detect_agent_role("Fix critical bug in load_context()")
        assert role == AgentRole.DEBUGGING

    def test_detect_testing_role_from_test_keywords(self) -> None:
        role = detect_agent_role("Increase test coverage for file_operations")
        assert role == AgentRole.TESTING

    def test_detect_quality_role_from_lint_keywords(self) -> None:
        role = detect_agent_role("Run lint and format for the project")
        assert role == AgentRole.QUALITY

    def test_detect_docs_role_from_docs_keywords(self) -> None:
        role = detect_agent_role("Update documentation and README")
        assert role == AgentRole.DOCS

    def test_detect_planning_role_from_plan_keywords(self) -> None:
        role = detect_agent_role("Create a new roadmap plan for Phase 60")
        assert role == AgentRole.PLANNING

    def test_detect_review_role_from_review_keywords(self) -> None:
        role = detect_agent_role("Code review for the new MCP tools")
        assert role == AgentRole.REVIEW

    def test_default_feature_role_when_no_keywords_match(self) -> None:
        role = detect_agent_role("Implement small feature for UI")
        assert role == AgentRole.FEATURE


class TestAgentRoleNormalization:
    """Tests for normalizing explicit role strings."""

    def test_normalize_exact_role_name(self) -> None:
        assert normalize_role_name("quality") == AgentRole.QUALITY

    def test_normalize_alias(self) -> None:
        assert normalize_role_name("lint") == AgentRole.QUALITY
        assert normalize_role_name("doc") == AgentRole.DOCS
        assert normalize_role_name("bugfix") == AgentRole.DEBUGGING

    def test_normalize_unknown_returns_none(self) -> None:
        assert normalize_role_name("unknown-role") is None

    def test_normalize_empty_returns_none(self) -> None:
        assert normalize_role_name("") is None
        assert normalize_role_name(None) is None  # type: ignore[arg-type]


class TestAgentRoleProfiles:
    """Sanity checks for role profiles."""

    def test_profiles_defined_for_all_roles(self) -> None:
        for role in AgentRole:
            profile = get_role_profile(role)
            assert profile.default_token_budget > 0

    def test_role_profiles_mapping_uses_same_instances(self) -> None:
        for role, profile in ROLE_PROFILES.items():
            assert get_role_profile(role) is profile
