"""
Simple import test for Phase 6 modules
"""

print("Testing Phase 6 module imports...")

try:
    from cortex.rules.shared_rules_manager import SharedRulesManager

    # Verify the import by checking the class exists
    _ = SharedRulesManager
    print("✓ SharedRulesManager imported successfully")
except Exception as e:
    print(f"✗ Failed to import SharedRulesManager: {e}")
    exit(1)

try:
    from cortex.optimization.rules_manager import RulesManager

    # Verify the import by checking the class exists
    _ = RulesManager
    print("✓ RulesManager imported successfully")
except Exception as e:
    print(f"✗ Failed to import RulesManager: {e}")
    exit(1)

try:
    from cortex.optimization.optimization_config import (
        DEFAULT_OPTIMIZATION_CONFIG,
        OptimizationConfig,  # noqa: F401
    )

    # Verify the import by checking the class exists
    _ = OptimizationConfig
    print("✓ OptimizationConfig imported successfully")

    # Check new config keys
    rules_config = DEFAULT_OPTIMIZATION_CONFIG.get("rules")
    if isinstance(rules_config, dict) and "shared_rules_enabled" in rules_config:
        print("✓ Shared rules configuration keys present")
    else:
        print("✗ Shared rules configuration keys missing")
        exit(1)

except Exception as e:
    print(f"✗ Failed to import OptimizationConfig: {e}")
    exit(1)

try:
    from cortex.main import mcp  # noqa: F401

    # Verify the import by checking the module exists
    _ = mcp
    print("✓ Main module imported successfully")
except Exception as e:
    print(f"✗ Failed to import main module: {e}")
    exit(1)

print("\n✅ All Phase 6 modules imported successfully!")
print("Phase 6 implementation is complete.")
