"""Unit tests for OptimizationConfig getter methods.

Covers convenience getters, new config getters, and tool search config.
Split from test_optimization_config.py to stay under 400 lines per file.
"""

from pathlib import Path
from typing import cast

import pytest

from cortex.core.models import JsonValue
from cortex.optimization.config import OptimizationConfig


class TestConvenienceMethods:
    """Tests for convenience getter methods."""

    def test_get_token_budget_returns_default_budget(
        self, temp_project_root: Path
    ) -> None:
        """Test get_token_budget returns default budget."""
        config = OptimizationConfig(temp_project_root)
        budget = config.get_token_budget()
        assert budget > 0
        assert isinstance(budget, int)

    def test_get_max_token_budget_returns_max_budget(
        self, temp_project_root: Path
    ) -> None:
        """Test get_max_token_budget returns maximum budget."""
        config = OptimizationConfig(temp_project_root)
        max_budget = config.get_max_token_budget()
        assert max_budget == 100000

    def test_get_loading_strategy_returns_strategy(
        self, temp_project_root: Path
    ) -> None:
        """Test get_loading_strategy returns default strategy."""
        config = OptimizationConfig(temp_project_root)
        strategy = config.get_loading_strategy()
        assert strategy == "dependency_aware"

    def test_get_mandatory_files_returns_list(self, temp_project_root: Path) -> None:
        """Test get_mandatory_files returns mandatory file list."""
        config = OptimizationConfig(temp_project_root)
        files = config.get_mandatory_files()
        assert isinstance(files, list)
        assert "projectBrief.md" in files

    def test_get_priority_order_returns_ordered_list(
        self, temp_project_root: Path
    ) -> None:
        """Test get_priority_order returns priority list."""
        config = OptimizationConfig(temp_project_root)
        order = config.get_priority_order()
        assert isinstance(order, list)
        assert len(order) == 6
        assert order[0] == "projectBrief.md"

    def test_is_summarization_enabled_returns_bool(
        self, temp_project_root: Path
    ) -> None:
        """Test is_summarization_enabled returns boolean."""
        config = OptimizationConfig(temp_project_root)
        enabled = config.is_summarization_enabled()
        assert enabled is True

    def test_get_summarization_strategy_returns_strategy(
        self, temp_project_root: Path
    ) -> None:
        """Test get_summarization_strategy returns strategy name."""
        config = OptimizationConfig(temp_project_root)
        strategy = config.get_summarization_strategy()
        assert strategy == "extract_key_sections"

    def test_get_summarization_target_reduction_returns_float(
        self, temp_project_root: Path
    ) -> None:
        """Test get_summarization_target_reduction returns reduction ratio."""
        config = OptimizationConfig(temp_project_root)
        reduction = config.get_summarization_target_reduction()
        assert reduction == 0.5

    def test_get_relevance_weights_returns_dict(self, temp_project_root: Path) -> None:
        """Test get_relevance_weights returns weight dictionary."""
        config = OptimizationConfig(temp_project_root)
        weights = config.get_relevance_weights()
        assert isinstance(weights, dict)
        assert "keyword_weight" in weights
        assert "dependency_weight" in weights
        assert "recency_weight" in weights
        assert "quality_weight" in weights
        assert sum(weights.values()) == pytest.approx(1.0)  # type: ignore[arg-type]

    def test_is_cache_enabled_returns_bool(self, temp_project_root: Path) -> None:
        """Test is_cache_enabled returns boolean."""
        config = OptimizationConfig(temp_project_root)
        enabled = config.is_cache_enabled()
        assert enabled is True

    def test_get_cache_ttl_returns_seconds(self, temp_project_root: Path) -> None:
        """Test get_cache_ttl returns TTL in seconds."""
        config = OptimizationConfig(temp_project_root)
        ttl = config.get_cache_ttl()
        assert ttl == 3600

    def test_is_rules_enabled_returns_bool(self, temp_project_root: Path) -> None:
        """Test is_rules_enabled returns boolean."""
        config = OptimizationConfig(temp_project_root)
        enabled = config.is_rules_enabled()
        assert enabled is False

    def test_get_rules_folder_returns_path(self, temp_project_root: Path) -> None:
        """Test get_rules_folder returns folder path."""
        config = OptimizationConfig(temp_project_root)
        folder = config.get_rules_folder()
        assert folder == ".cortex/rules"

    def test_is_self_evolution_enabled_returns_bool(
        self, temp_project_root: Path
    ) -> None:
        """Test is_self_evolution_enabled returns boolean."""
        config = OptimizationConfig(temp_project_root)
        enabled = config.is_self_evolution_enabled()
        assert enabled is True


class TestNewConfigGetters:
    """Tests for newly added configuration getter methods."""

    def test_get_reserve_for_response_returns_int(
        self, temp_project_root: Path
    ) -> None:
        """Test get_reserve_for_response returns integer."""
        config = OptimizationConfig(temp_project_root)
        reserve = config.get_reserve_for_response()
        assert reserve == 10000
        assert isinstance(reserve, int)

    def test_is_summarization_cache_enabled_returns_bool(
        self, temp_project_root: Path
    ) -> None:
        """Test is_summarization_cache_enabled returns boolean."""
        config = OptimizationConfig(temp_project_root)
        enabled = config.is_summarization_cache_enabled()
        assert enabled is True
        assert isinstance(enabled, bool)

    def test_get_summarization_age_threshold_days_returns_int(
        self, temp_project_root: Path
    ) -> None:
        """Test get_summarization_age_threshold_days returns integer."""
        config = OptimizationConfig(temp_project_root)
        threshold = config.get_summarization_age_threshold_days()
        assert threshold == 90
        assert isinstance(threshold, int)

    def test_is_auto_summarize_old_files_returns_bool(
        self, temp_project_root: Path
    ) -> None:
        """Test is_summarization_auto_summarize_old_files returns boolean."""
        config = OptimizationConfig(temp_project_root)
        auto_summarize = config.is_summarization_auto_summarize_old_files()
        assert auto_summarize is False
        assert isinstance(auto_summarize, bool)

    def test_get_max_cache_size_mb_returns_int(self, temp_project_root: Path) -> None:
        """Test get_max_cache_size_mb returns integer."""
        config = OptimizationConfig(temp_project_root)
        max_size = config.get_max_cache_size_mb()
        assert max_size == 50
        assert isinstance(max_size, int)

    def test_get_rule_priority_returns_str(self, temp_project_root: Path) -> None:
        """Test get_rule_priority returns string."""
        config = OptimizationConfig(temp_project_root)
        priority = config.get_rule_priority()
        assert priority == "local_overrides_shared"
        assert isinstance(priority, str)

    def test_is_context_aware_loading_returns_bool(
        self, temp_project_root: Path
    ) -> None:
        """Test is_context_aware_loading returns boolean."""
        config = OptimizationConfig(temp_project_root)
        context_aware = config.is_context_aware_loading()
        assert context_aware is True
        assert isinstance(context_aware, bool)

    def test_is_always_include_generic_returns_bool(
        self, temp_project_root: Path
    ) -> None:
        """Test is_always_include_generic returns boolean."""
        config = OptimizationConfig(temp_project_root)
        always_include = config.is_always_include_generic()
        assert always_include is True
        assert isinstance(always_include, bool)

    def test_is_optimization_enabled_returns_bool(
        self, temp_project_root: Path
    ) -> None:
        """Test is_optimization_enabled returns boolean."""
        config = OptimizationConfig(temp_project_root)
        enabled = config.is_optimization_enabled()
        assert enabled is True
        assert isinstance(enabled, bool)

    def test_new_getters_use_config_values(self, temp_project_root: Path) -> None:
        """Test new getters use values from configuration."""
        config = OptimizationConfig(temp_project_root)
        _ = config.set("token_budget.reserve_for_response", 15000)
        _ = config.set("summarization.cache_summaries", False)
        _ = config.set("rules.rule_priority", "shared_overrides_local")
        _ = config.set("enabled", False)
        assert config.get_reserve_for_response() == 15000
        assert config.is_summarization_cache_enabled() is False
        assert config.get_rule_priority() == "shared_overrides_local"
        assert config.is_optimization_enabled() is False

    def test_new_getters_use_defaults_when_missing(
        self, temp_project_root: Path
    ) -> None:
        """Test new getters fall back to defaults when config keys missing."""
        config = OptimizationConfig(temp_project_root)
        config.config = cast(
            dict[str, JsonValue],
            {
                "token_budget": {},
                "summarization": {},
                "performance": {},
                "rules": {},
            },
        )
        assert config.get_reserve_for_response() == 10000
        assert config.is_summarization_cache_enabled() is True
        assert config.get_summarization_age_threshold_days() == 90
        assert config.get_max_cache_size_mb() == 50
        assert config.get_rule_priority() == "local_overrides_shared"
        assert config.is_context_aware_loading() is True
        assert config.is_always_include_generic() is True
        assert config.is_optimization_enabled() is True

    def test_get_language_keywords_returns_dict(self, temp_project_root: Path) -> None:
        """Test get_language_keywords returns dictionary."""
        config = OptimizationConfig(temp_project_root)
        keywords = config.get_language_keywords()
        assert isinstance(keywords, dict)
        assert "python" in keywords
        assert isinstance(keywords["python"], list)
        assert "python" in keywords["python"]

    def test_get_language_keywords_uses_config_values(
        self, temp_project_root: Path
    ) -> None:
        """Test get_language_keywords uses values from configuration."""
        config = OptimizationConfig(temp_project_root)
        keywords = config.get_language_keywords()
        assert isinstance(keywords, dict)
        assert "python" in keywords
        assert isinstance(keywords["python"], list)
        assert "python" in keywords["python"]


class TestGetToolSearchConfig:
    """Tests for get_tool_search_config (Phase 49 Step 6)."""

    def test_returns_expected_keys(self, temp_project_root: Path) -> None:
        """get_tool_search_config returns expected keys."""
        config = OptimizationConfig(temp_project_root)
        ts = config.get_tool_search_config()
        assert isinstance(ts, dict)
        assert "enabled" in ts
        assert "always_loaded" in ts
        assert "deferred_medium" in ts
        assert "deferred_low" in ts
        assert isinstance(ts["always_loaded"], list)
        assert isinstance(ts["deferred_medium"], list)
        assert isinstance(ts["deferred_low"], list)

    def test_token_savings_potential(self, temp_project_root: Path) -> None:
        """always_loaded count < total so deferred loading reduces initial tokens."""
        config = OptimizationConfig(temp_project_root)
        ts = config.get_tool_search_config()
        always = cast(list[str], ts["always_loaded"])
        medium = cast(list[str], ts["deferred_medium"])
        low = cast(list[str], ts["deferred_low"])
        total = len(always) + len(medium) + len(low)
        assert len(always) < total
        assert len(always) >= 7
        assert len(medium) + len(low) >= 2
