"""
Test suite for Phase 6: Shared Rules Repository

Tests the SynapseManager module and integration with RulesManager.
"""

import json
import tempfile
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.token_counter import TokenCounter
from cortex.optimization.rules_manager import RulesManager
from cortex.rules.synapse_manager import SynapseManager


async def test_synapse_manager_initialization():
    """Test SynapseManager initialization."""
    print("Testing SynapseManager initialization...")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        manager = SynapseManager(
            project_root=project_root, synapse_folder=".cortex/synapse"
        )

        assert manager.project_root == project_root
        assert manager.synapse_path == project_root / ".cortex/synapse"
        assert manager.manifest is None
        print("✓ SynapseManager initialized successfully")


async def test_context_detection():
    """Test context detection from task description."""
    print("Testing context detection...")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        manager = SynapseManager(project_root=project_root)

        # Test Python context
        context = await manager.detect_context(
            task_description="Implement JWT authentication in Django using pytest",
            project_files=None,
        )

        detected_languages = context.get("detected_languages")
        assert isinstance(detected_languages, (list, set, tuple))
        assert "python" in detected_languages
        detected_frameworks = context.get("detected_frameworks")
        assert isinstance(detected_frameworks, (list, set, tuple))
        assert "django" in detected_frameworks
        assert context["task_type"] == "authentication"
        print("✓ Python/Django context detected")

        # Test Swift context
        context = await manager.detect_context(
            task_description="Build a SwiftUI view with UIKit integration",
            project_files=None,
        )

        detected_languages = context.get("detected_languages")
        assert isinstance(detected_languages, (list, set, tuple))
        assert "swift" in detected_languages
        detected_frameworks = context.get("detected_frameworks")
        assert isinstance(detected_frameworks, (list, set, tuple))
        assert "swiftui" in detected_frameworks
        assert context["task_type"] == "ui"
        print("✓ Swift/SwiftUI context detected")

        # Test with project files
        test_files = [Path("auth.py"), Path("views.py"), Path("test_auth.py")]
        context = await manager.detect_context(
            task_description="Test the authentication system", project_files=test_files
        )

        detected_languages = context.get("detected_languages")
        assert isinstance(detected_languages, (list, set, tuple))
        assert "python" in detected_languages
        assert context.get("task_type") == "testing"
        print("✓ Context detection from project files works")


async def test_get_relevant_categories():
    """Test getting relevant categories from context."""
    print("Testing get_relevant_categories...")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        manager = SynapseManager(project_root=project_root)

        context = {
            "detected_languages": ["python"],
            "detected_frameworks": ["django"],
            "task_type": "authentication",
            "categories_to_load": ["generic", "python", "authentication"],
        }

        context_dict: dict[str, object] = {
            "detected_languages": context["detected_languages"],
            "detected_frameworks": context["detected_frameworks"],
            "task_type": context["task_type"],
            "categories_to_load": context["categories_to_load"],
        }
        categories = await manager.get_relevant_categories(context=context_dict)

        assert "generic" in categories
        assert "python" in categories
        assert "authentication" in categories
        print("✓ Relevant categories identified")


async def test_rules_manifest_loading():
    """Test loading rules manifest."""
    print("Testing rules manifest loading...")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        synapse_path = project_root / ".cortex/synapse"
        synapse_path.mkdir(parents=True)
        rules_path = synapse_path / "rules"
        rules_path.mkdir()

        # Create a mock manifest
        manifest = {
            "version": "1.0",
            "last_updated": "2025-12-20T10:00:00Z",
            "categories": {
                "generic": {
                    "description": "Universal coding standards",
                    "always_include": True,
                    "rules": [
                        {
                            "file": "coding-standards.md",
                            "priority": 100,
                            "keywords": ["code", "standards", "quality"],
                        }
                    ],
                },
                "python": {
                    "description": "Python-specific rules",
                    "always_include": False,
                    "rules": [
                        {
                            "file": "style-guide.md",
                            "priority": 100,
                            "keywords": ["python", "pep8", "style"],
                        }
                    ],
                },
            },
        }

        manifest_path = rules_path / "rules-manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        manager = SynapseManager(
            project_root=project_root, synapse_folder=".cortex/synapse"
        )

        loaded_manifest = await manager.load_rules_manifest()

        assert loaded_manifest is not None
        assert loaded_manifest["version"] == "1.0"
        categories = loaded_manifest.get("categories")
        assert isinstance(categories, dict)
        assert "generic" in categories
        assert "python" in categories
        print("✓ Rules manifest loaded successfully")


async def test_load_category():
    """Test loading rules from a category."""
    print("Testing load_category...")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        synapse_path = project_root / ".cortex/synapse"
        synapse_path.mkdir(parents=True)
        rules_path = synapse_path / "rules"
        rules_path.mkdir()

        # Create category folder and rule file
        generic_path = rules_path / "generic"
        generic_path.mkdir()

        rule_content = "# Coding Standards\n\nAlways write clean code."
        rule_file = generic_path / "coding-standards.md"
        with open(rule_file, "w") as f:
            _ = f.write(rule_content)

        # Create manifest
        manifest = {
            "version": "1.0",
            "categories": {
                "generic": {
                    "description": "Universal coding standards",
                    "rules": [
                        {
                            "file": "coding-standards.md",
                            "priority": 100,
                            "keywords": ["code", "standards"],
                        }
                    ],
                }
            },
        }

        manifest_path = rules_path / "rules-manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        manager = SynapseManager(
            project_root=project_root, synapse_folder=".cortex/synapse"
        )

        _ = await manager.load_rules_manifest()
        rules = await manager.load_category("generic")

        assert len(rules) == 1
        assert rules[0]["file"] == "coding-standards.md"
        assert rules[0]["content"] == rule_content
        assert rules[0]["priority"] == 100
        print("✓ Category rules loaded successfully")


async def test_merge_rules():
    """Test merging shared and local rules."""
    print("Testing merge_rules...")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        manager = SynapseManager(project_root=project_root)

        shared_rules = [
            {"file": "rule1.md", "content": "Shared rule 1", "priority": 100},
            {"file": "rule2.md", "content": "Shared rule 2", "priority": 90},
        ]

        local_rules = [
            {"file": "rule2.md", "content": "Local override", "priority": 95},
            {"file": "rule3.md", "content": "Local rule 3", "priority": 85},
        ]

        # Test local overrides shared
        shared_rules_typed: list[dict[str, object]] = [
            {k: v for k, v in rule.items()} for rule in shared_rules
        ]
        local_rules_typed: list[dict[str, object]] = [
            {k: v for k, v in rule.items()} for rule in local_rules
        ]
        merged = await manager.merge_rules(
            shared_rules=shared_rules_typed,
            local_rules=local_rules_typed,
            priority="local_overrides_shared",
        )

        # Should have 3 rules: rule1 (shared), rule2 (local), rule3 (local)
        assert len(merged) == 3
        rule2 = [r for r in merged if r["file"] == "rule2.md"][0]
        assert rule2["content"] == "Local override"
        print("✓ Local overrides shared works")

        # Test shared overrides local
        merged = await manager.merge_rules(
            shared_rules=shared_rules_typed,
            local_rules=local_rules_typed,
            priority="shared_overrides_local",
        )

        assert len(merged) == 3
        rule2 = [r for r in merged if r["file"] == "rule2.md"][0]
        assert rule2["content"] == "Shared rule 2"
        print("✓ Shared overrides local works")


async def test_rules_manager_integration():
    """Test RulesManager integration with SynapseManager."""
    print("Testing RulesManager integration...")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Setup file system manager
        fs_manager = FileSystemManager(project_root)
        metadata_index = MetadataIndex(project_root)
        token_counter = TokenCounter()

        # Create synapse manager
        synapse_manager = SynapseManager(
            project_root=project_root, synapse_folder=".cortex/synapse"
        )

        # Create rules manager with synapse support
        rules_manager = RulesManager(
            project_root=project_root,
            file_system=fs_manager,
            metadata_index=metadata_index,
            token_counter=token_counter,
            rules_folder=".cursorrules",
            synapse_manager=synapse_manager,
        )

        # Test that synapse manager is set
        assert rules_manager.synapse_manager is not None
        print("✓ RulesManager integrated with SynapseManager")


async def test_get_relevant_rules_with_context():
    """Test get_relevant_rules with context-aware loading."""
    print("Testing get_relevant_rules with context...")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Setup managers
        fs_manager = FileSystemManager(project_root)
        metadata_index = MetadataIndex(project_root)
        token_counter = TokenCounter()

        # Create synapse structure
        synapse_path = project_root / ".cortex/synapse"
        synapse_path.mkdir(parents=True)
        rules_path = synapse_path / "rules"
        rules_path.mkdir()

        # Create generic category
        generic_path = rules_path / "generic"
        generic_path.mkdir()

        generic_rule = generic_path / "coding-standards.md"
        with open(generic_rule, "w") as f:
            _ = f.write("# Coding Standards\n\nWrite clean code.")

        # Create python category
        python_path = rules_path / "python"
        python_path.mkdir()

        python_rule = python_path / "style-guide.md"
        with open(python_rule, "w") as f:
            _ = f.write("# Python Style Guide\n\nFollow PEP 8.")

        # Create manifest
        manifest = {
            "version": "1.0",
            "categories": {
                "generic": {
                    "rules": [
                        {
                            "file": "coding-standards.md",
                            "priority": 100,
                            "keywords": ["code"],
                        }
                    ]
                },
                "python": {
                    "rules": [
                        {
                            "file": "style-guide.md",
                            "priority": 100,
                            "keywords": ["python"],
                        }
                    ]
                },
            },
        }

        manifest_path = rules_path / "rules-manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        # Create synapse and rules managers
        synapse_manager = SynapseManager(
            project_root=project_root, synapse_folder=".cortex/synapse"
        )

        rules_manager = RulesManager(
            project_root=project_root,
            file_system=fs_manager,
            metadata_index=metadata_index,
            token_counter=token_counter,
            synapse_manager=synapse_manager,
        )

        # Get relevant rules
        result = await rules_manager.get_relevant_rules(
            task_description="Write Python code with proper testing",
            max_tokens=10000,
            min_relevance_score=0.0,
            project_files=None,
            context_aware=True,
        )

        assert result.get("source") == "hybrid"
        context_result_raw = result.get("context")
        assert isinstance(context_result_raw, dict)
        context_result = cast(dict[str, object], context_result_raw)
        detected_languages_result_raw = context_result.get("detected_languages")
        assert isinstance(detected_languages_result_raw, (list, set, tuple))
        detected_languages_result = cast(
            list[str] | set[str] | tuple[str, ...], detected_languages_result_raw
        )
        assert "python" in detected_languages_result
        print("✓ Context-aware rule loading works")


async def run_all_tests():
    """Run all Phase 6 tests."""
    print("\n" + "=" * 60)
    print("Phase 6: Shared Rules Repository - Test Suite")
    print("=" * 60 + "\n")

    tests = [
        ("SynapseManager Initialization", test_synapse_manager_initialization),
        ("Context Detection", test_context_detection),
        ("Get Relevant Categories", test_get_relevant_categories),
        ("Rules Manifest Loading", test_rules_manifest_loading),
        ("Load Category", test_load_category),
        ("Merge Rules", test_merge_rules),
        ("RulesManager Integration", test_rules_manager_integration),
        ("Get Relevant Rules with Context", test_get_relevant_rules_with_context),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except Exception as e:
            print(f"✗ {name} FAILED: {e}")
            failed += 1
        print()

    print("=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n✅ All Phase 6 tests passed!")
    else:
        print(f"\n❌ {failed} test(s) failed")

    return failed == 0


if __name__ == "__main__":
    import asyncio

    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
