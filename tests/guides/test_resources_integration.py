"""Tests for cortex.resources GUIDES integration with cortex.guides."""

from cortex.guides.benefits import GUIDE as BENEFITS_GUIDE
from cortex.guides.setup import GUIDE as SETUP_GUIDE
from cortex.guides.structure import GUIDE as STRUCTURE_GUIDE
from cortex.guides.usage import GUIDE as USAGE_GUIDE
from cortex.resources import GUIDES


class TestResourcesGuidesIntegration:
    """Tests that resources.GUIDES exposes all guide modules correctly."""

    def test_guides_contains_all_four_keys(self) -> None:
        """GUIDES dict has setup, usage, benefits, structure."""
        assert set(GUIDES.keys()) == {"setup", "usage", "benefits", "structure"}

    def test_setup_guide_matches_module(self) -> None:
        """GUIDES['setup'] equals cortex.guides.setup.GUIDE."""
        assert GUIDES["setup"] is SETUP_GUIDE

    def test_usage_guide_matches_module(self) -> None:
        """GUIDES['usage'] equals cortex.guides.usage.GUIDE."""
        assert GUIDES["usage"] is USAGE_GUIDE

    def test_benefits_guide_matches_module(self) -> None:
        """GUIDES['benefits'] equals cortex.guides.benefits.GUIDE."""
        assert GUIDES["benefits"] is BENEFITS_GUIDE

    def test_structure_guide_matches_module(self) -> None:
        """GUIDES['structure'] equals cortex.guides.structure.GUIDE."""
        assert GUIDES["structure"] is STRUCTURE_GUIDE

    def test_all_guides_non_empty_strings(self) -> None:
        """Every value in GUIDES is a non-empty string."""
        for name, content in GUIDES.items():
            assert isinstance(content, str), f"{name!r} is not str"
            assert len(content) > 0, f"{name!r} is empty"
