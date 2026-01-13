# Function Length Violations Report

**Total Violations:** 102
**Files Affected:** 43

## Top 50 Violations (by severity)

| # | File | Function | Lines | Over Limit | Location |
|---|------|----------|-------|------------|----------|
| 1 | learning_engine.py | `adjust_suggestion_confidence` | 70 | +40 🟠 | src/cortex/refactoring/learning_engine.py:283 |
| 2 | structure_analyzer.py | `analyze_file_organization` | 69 | +39 🟠 | src/cortex/analysis/structure_analyzer.py:50 |
| 3 | execution_validator.py | `validate_refactoring` | 69 | +39 🟠 | src/cortex/refactoring/execution_validator.py:59 |
| 4 | rollback_manager.py | `rollback_refactoring` | 68 | +38 🟠 | src/cortex/refactoring/rollback_manager.py:152 |
| 5 | relevance_scorer.py | `extract_keywords` | 67 | +37 🟠 | src/cortex/optimization/relevance_scorer.py:207 |
| 6 | phase4_optimization.py | `load_progressive_context` | 65 | +35 🟠 | src/cortex/tools/phase4_optimization.py:123 |
| 7 | rules_indexer.py | `index_rules` | 65 | +35 🟠 | src/cortex/optimization/rules_indexer.py:52 |
| 8 | reorganization_planner.py | `analyze_current_structure` | 64 | +34 🟠 | src/cortex/refactoring/reorganization_planner.py:168 |
| 9 | adaptation_config.py | `validate` | 63 | +33 🟠 | src/cortex/refactoring/adaptation_config.py:343 |
| 10 | learning_engine.py | `_update_preferences` | 63 | +33 🟠 | src/cortex/refactoring/learning_engine.py:206 |
| 11 | optimization_strategies.py | `optimize_with_sections` | 62 | +32 🟠 | src/cortex/optimization/optimization_strategies.py:210 |
| 12 | structure_analyzer.py | `find_dependency_chains` | 61 | +31 🟠 | src/cortex/analysis/structure_analyzer.py:635 |
| 13 | shared_rules_manager.py | `update_shared_rule` | 60 | +30 🟠 | src/cortex/rules/shared_rules_manager.py:581 |
| 14 | learning_engine.py | `get_learning_insights` | 60 | +30 🟠 | src/cortex/refactoring/learning_engine.py:440 |
| 15 | phase1_foundation.py | `get_version_history` | 59 | +29 🟠 | src/cortex/tools/phase1_foundation.py:85 |
| 16 | migration.py | `migrate` | 59 | +29 🟠 | src/cortex/core/migration.py:97 |
| 17 | refactoring_engine.py | `generate_actions` | 59 | +29 🟠 | src/cortex/refactoring/refactoring_engine.py:289 |
| 18 | structure_migration.py | `migrate_legacy_structure` | 59 | +29 🟠 | src/cortex/structure/structure_migration.py:78 |
| 19 | structure_migration.py | `_migrate_tradewing_style` | 59 | +29 🟠 | src/cortex/structure/structure_migration.py:167 |
| 20 | phase2_linking.py | `get_link_graph` | 58 | +28 🟠 | src/cortex/tools/phase2_linking.py:394 |
| 21 | validation_operations.py | `validate` | 58 | +28 🟠 | src/cortex/tools/validation_operations.py:209 |
| 22 | phase8_structure.py | `check_structure_health` | 57 | +27 🟠 | src/cortex/tools/phase8_structure.py:30 |
| 23 | insight_engine.py | `_generate_quality_insights` | 57 | +27 🟠 | src/cortex/analysis/insight_engine.py:718 |
| 24 | metadata_index.py | `update_usage_analytics` | 56 | +26 🟠 | src/cortex/core/metadata_index.py:638 |
| 25 | phase5_execution.py | `apply_refactoring` | 55 | +25 🟠 | src/cortex/tools/phase5_execution.py:166 |
| 26 | phase4_optimization.py | `optimize_context` | 53 | +23 🟠 | src/cortex/tools/phase4_optimization.py:32 |
| 27 | consolidation_detector.py | `detect_similar_sections` | 53 | +23 🟠 | src/cortex/refactoring/consolidation_detector.py:245 |
| 28 | consolidation_detector.py | `detect_shared_patterns` | 53 | +23 🟠 | src/cortex/refactoring/consolidation_detector.py:321 |
| 29 | link_validator.py | `validate_file` | 53 | +23 🟠 | src/cortex/linking/link_validator.py:35 |
| 30 | relevance_scorer.py | `score_files` | 52 | +22 🟠 | src/cortex/optimization/relevance_scorer.py:46 |
| 31 | progressive_loader.py | `load_by_relevance` | 52 | +22 🟠 | src/cortex/optimization/progressive_loader.py:196 |
| 32 | context_optimizer.py | `optimize_context` | 52 | +22 🟠 | src/cortex/optimization/context_optimizer.py:58 |
| 33 | link_validator.py | `generate_report` | 52 | +22 🟠 | src/cortex/linking/link_validator.py:358 |
| 34 | link_parser.py | `parse_file` | 52 | +22 🟠 | src/cortex/linking/link_parser.py:29 |
| 35 | structure_analyzer.py | `assess_complexity` | 51 | +21 🟠 | src/cortex/analysis/structure_analyzer.py:559 |
| 36 | shared_rules_manager.py | `load_category` | 51 | +21 🟠 | src/cortex/rules/shared_rules_manager.py:449 |
| 37 | phase4_optimization.py | `get_relevance_scores` | 50 | +20 🟡 | src/cortex/tools/phase4_optimization.py:281 |
| 38 | learning_engine.py | `get_learning_recommendations` | 50 | +20 🟡 | src/cortex/refactoring/learning_engine.py:534 |
| 39 | reorganization_planner.py | `needs_reorganization` | 50 | +20 🟡 | src/cortex/refactoring/reorganization_planner.py:293 |
| 40 | optimization_strategies.py | `optimize_by_dependencies` | 49 | +19 🟡 | src/cortex/optimization/optimization_strategies.py:124 |
| 41 | refactoring_engine.py | `generate_suggestions` | 49 | +19 🟡 | src/cortex/refactoring/refactoring_engine.py:132 |
| 42 | rollback_manager.py | `restore_files` | 49 | +19 🟡 | src/cortex/refactoring/rollback_manager.py:353 |
| 43 | pattern_analyzer.py | `get_access_frequency` | 48 | +18 🟡 | src/cortex/analysis/pattern_analyzer.py:260 |
| 44 | summarization_engine.py | `summarize_file` | 48 | +18 🟡 | src/cortex/optimization/summarization_engine.py:44 |
| 45 | insight_engine.py | `generate_summary` | 47 | +17 🟡 | src/cortex/analysis/insight_engine.py:789 |
| 46 | refactoring_engine.py | `generate_from_insight` | 47 | +17 🟡 | src/cortex/refactoring/refactoring_engine.py:223 |
| 47 | consolidation_detector.py | `detect_exact_duplicates` | 47 | +17 🟡 | src/cortex/refactoring/consolidation_detector.py:174 |
| 48 | insight_engine.py | `generate_insights` | 46 | +16 🟡 | src/cortex/analysis/insight_engine.py:82 |
| 49 | quality_metrics.py | `calculate_overall_score` | 46 | +16 🟡 | src/cortex/validation/quality_metrics.py:38 |
| 50 | file_operations.py | `manage_file` | 45 | +15 🟡 | src/cortex/tools/file_operations.py:28 |

## Summary by File

| File | Violations | Total Over Limit |
|------|------------|------------------|
| learning_engine.py | 7 | +133 |
| reorganization_planner.py | 6 | +71 |
| rollback_manager.py | 5 | +81 |
| refactoring_engine.py | 5 | +73 |
| optimization_strategies.py | 4 | +63 |
| pattern_analyzer.py | 4 | +45 |
| summarization_engine.py | 4 | +42 |
| structure_analyzer.py | 3 | +91 |
| phase4_optimization.py | 3 | +78 |
| phase1_foundation.py | 3 | +35 |
| structure_migration.py | 3 | +59 |
| phase2_linking.py | 3 | +45 |
| insight_engine.py | 3 | +60 |
| consolidation_detector.py | 3 | +63 |
| link_validator.py | 3 | +58 |
| progressive_loader.py | 3 | +38 |
| container.py | 3 | +21 |
| relevance_scorer.py | 2 | +59 |
| adaptation_config.py | 2 | +47 |
| shared_rules_manager.py | 2 | +51 |
| phase5_execution.py | 2 | +34 |
| quality_metrics.py | 2 | +17 |
| file_operations.py | 2 | +20 |
| refactoring_executor.py | 2 | +24 |
| context_detector.py | 2 | +15 |
| split_recommender.py | 2 | +12 |
| structure_lifecycle.py | 2 | +17 |
| duplication_detector.py | 2 | +6 |
| execution_validator.py | 1 | +39 |
| rules_indexer.py | 1 | +35 |
