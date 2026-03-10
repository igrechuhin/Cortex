"""Unit tests for roadmap section constants and auto-creation."""

from cortex.tools.plans.register_helpers import (
    parse_roadmap_sections,
    register_plan_entry,
)
from cortex.validation.roadmap_models import (
    KEY_TO_SECTION,
    SECTION_TO_KEY,
    RoadmapSection,
)


class TestRoadmapSectionEnum:
    """Tests for RoadmapSection StrEnum."""

    def test_all_values_match_expected_headers(self) -> None:
        """Verify enum values match the canonical roadmap headers."""
        # Arrange & Act & Assert
        assert RoadmapSection.BLOCKERS == "Blockers (ASAP Priority)"
        assert RoadmapSection.ACTIVE_WORK == "Active Work (in progress)"
        assert RoadmapSection.FUTURE == "Future Enhancements"
        assert RoadmapSection.PENDING == "Pending plans (from .cortex/plans)"

    def test_section_to_key_covers_all_enum_values(self) -> None:
        """Every enum member has a corresponding key mapping."""
        # Arrange & Act
        mapped_headers = set(SECTION_TO_KEY.keys())
        enum_values = {s.value for s in RoadmapSection}

        # Assert
        assert mapped_headers == enum_values

    def test_key_to_section_is_inverse(self) -> None:
        """KEY_TO_SECTION is the exact inverse of SECTION_TO_KEY."""
        # Arrange & Act & Assert
        for header, key in SECTION_TO_KEY.items():
            assert KEY_TO_SECTION[key] == header


class TestRoadmapAutoCreation:
    """Tests for auto-creation of missing roadmap sections."""

    def test_register_succeeds_when_section_exists(self) -> None:
        """Registration works normally when section is present."""
        # Arrange
        content = (
            "# Roadmap\n\n"
            "## Blockers (ASAP Priority)\n\n"
            "## Active Work (in progress)\n\n"
            "## Future Enhancements\n\n"
            "## Pending plans (from .cortex/plans)\n\n"
        )

        # Act
        updated, line = register_plan_entry(
            content, "Test Plan", "A test plan", "PENDING", "pending"
        )

        # Assert
        assert line is not None
        assert "Test Plan" in updated

    def test_register_auto_creates_missing_section(self) -> None:
        """Registration auto-creates a section if it's missing."""
        # Arrange — roadmap with NO pending section
        content = (
            "# Roadmap\n\n"
            "## Blockers (ASAP Priority)\n\n"
            "## Active Work (in progress)\n\n"
        )

        # Act
        updated, line = register_plan_entry(
            content, "New Plan", "Description", "PENDING", "pending"
        )

        # Assert
        assert "Pending plans (from .cortex/plans)" in updated
        assert line is not None
        assert "New Plan" in updated

    def test_parse_uses_constants(self) -> None:
        """parse_roadmap_sections uses SECTION_TO_KEY, not hardcoded strings."""
        # Arrange
        content = (
            "# Roadmap\n\n"
            "## Blockers (ASAP Priority)\n\n"
            "- blocker item\n\n"
            "## Pending plans (from .cortex/plans)\n\n"
            "- pending item\n"
        )

        # Act
        sections = parse_roadmap_sections(content)

        # Assert
        assert "blockers" in sections
        assert "pending" in sections
