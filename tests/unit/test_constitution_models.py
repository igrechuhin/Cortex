"""Tests for constitutional governance models."""

from datetime import date

import pytest
from pydantic import ValidationError

from cortex.core.models import ConstitutionDoc


class TestConstitutionDoc:
    """Validation tests for ConstitutionDoc."""

    def test_accepts_expected_fields(self) -> None:
        """Model validates the planned schema fields and values."""
        # Arrange
        payload = {
            "principles": ["No Any types", "Small functions"],
            "tech_stack": ["Python", "Pydantic"],
            "hard_limits": ["Functions <= 30 lines"],
            "compliance_requirements": ["Plans must include governance check"],
            "created": date(2026, 4, 6),
            "last_updated": date(2026, 4, 6),
        }

        # Act
        model = ConstitutionDoc.model_validate(payload)

        # Assert
        assert model.principles == ["No Any types", "Small functions"]
        assert model.created == date(2026, 4, 6)
        assert model.last_updated == date(2026, 4, 6)

    def test_rejects_unknown_fields(self) -> None:
        """Extra fields are forbidden to keep constitution schema stable."""
        # Arrange
        payload: dict[str, object] = {
            "principles": [],
            "tech_stack": [],
            "hard_limits": [],
            "compliance_requirements": [],
            "created": date(2026, 4, 6),
            "last_updated": date(2026, 4, 6),
            "unexpected": "value",
        }

        # Act / Assert
        with pytest.raises(ValidationError):
            _ = ConstitutionDoc.model_validate(payload)
