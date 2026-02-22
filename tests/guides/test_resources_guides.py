"""Tests for guides integration in cortex.resources."""

from cortex.guides.benefits import GUIDE as BENEFITS_GUIDE
from cortex.guides.setup import GUIDE as SETUP_GUIDE
from cortex.guides.structure import GUIDE as STRUCTURE_GUIDE
from cortex.guides.usage import GUIDE as USAGE_GUIDE
from cortex.resources import GUIDES


class TestResourcesGuidesDict:
    """GUIDES dict in resources aggregates all guides."""

    def test_has_all_four_guides(self) -> None:
        """GUIDES contains setup, usage, benefits, structure."""
        assert set(GUIDES.keys()) == {"setup", "usage", "benefits", "structure"}

    def test_setup_matches_module(self) -> None:
        """GUIDES['setup'] is the same object as SETUP_GUIDE."""
        assert GUIDES["setup"] is SETUP_GUIDE

    def test_usage_matches_module(self) -> None:
        """GUIDES['usage'] is the same object as USAGE_GUIDE."""
        assert GUIDES["usage"] is USAGE_GUIDE

    def test_benefits_matches_module(self) -> None:
        """GUIDES['benefits'] is the same object as BENEFITS_GUIDE."""
        assert GUIDES["benefits"] is BENEFITS_GUIDE

    def test_structure_matches_module(self) -> None:
        """GUIDES['structure'] is the same object as STRUCTURE_GUIDE."""
        assert GUIDES["structure"] is STRUCTURE_GUIDE

    def test_all_values_are_non_empty_strings(self) -> None:
        """Every guide value is a non-empty string."""
        for key, value in GUIDES.items():
            assert isinstance(value, str), f"{key!r} is not str: {type(value)}"
            assert len(value.strip()) > 0, f"{key!r} guide is empty"
