"""
Import smoke tests for Phase 6 modules (Synapse rules, optimization, MCP server).
"""


def test_synapse_manager_import() -> None:
    from cortex.rules.synapse_manager import SynapseManager

    assert SynapseManager is not None


def test_rules_manager_import() -> None:
    from cortex.optimization.rules_manager import RulesManager

    assert RulesManager is not None


def test_optimization_config_import() -> None:
    from cortex.optimization.config import (
        DEFAULT_OPTIMIZATION_CONFIG,
        OptimizationConfig,
    )

    assert OptimizationConfig is not None
    rules_config = DEFAULT_OPTIMIZATION_CONFIG.get("rules")
    assert rules_config is None or isinstance(rules_config, dict)


def test_mcp_server_module_import() -> None:
    from cortex.server import mcp  # noqa: F401

    assert mcp is not None
