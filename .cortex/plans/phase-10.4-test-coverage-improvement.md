# Phase 10.4: Test Coverage Improvement Plan

## Objective

Increase test coverage from **88.52%** to **90%+** by adding comprehensive tests for modules with low or zero coverage.

## Current Status

- **Current Coverage**: 88.52%
- **Target Coverage**: 90.00%
- **Gap**: 1.48%
- **Total Statements**: 11,921
- **Uncovered Statements**: 1,153

## Priority Modules (Ordered by Impact)

### Tier 1: Zero Coverage (Critical - Easy Wins)

#### 1. `src/cortex/resources.py` (0.00% - 13 statements)

- **Impact**: +0.11% coverage if brought to 90%
- **Complexity**: Low
- **Estimated Time**: 30 minutes
- **Test File**: `tests/unit/test_resources.py` (NEW)

**What to Test:**

- `TEMPLATES` dictionary contains all expected keys
- `GUIDES` dictionary contains all expected keys
- Template values are non-empty strings
- Guide values are non-empty strings
- All template keys match expected memory bank file names
- All guide keys match expected guide names

**Test Cases:**

```python
- test_templates_dict_structure()
- test_templates_all_keys_present()
- test_templates_all_values_are_strings()
- test_templates_all_values_non_empty()
- test_guides_dict_structure()
- test_guides_all_keys_present()
- test_guides_all_values_are_strings()
- test_guides_all_values_non_empty()
```

#### 2. `src/cortex/managers/manager_groups.py` (0.00% - 9 statements)

- **Impact**: +0.07% coverage if brought to 90%
- **Complexity**: Low
- **Estimated Time**: 30 minutes
- **Test File**: `tests/unit/test_manager_groups.py` (NEW)

**What to Test:**

- `ManagerGroup` data class initialization
- `ManagerGroup.__str__()` method
- `MANAGER_GROUPS` list structure
- All manager groups have valid names, managers, and priorities
- Manager group priorities are in valid range (1-4)
- Manager names in groups are valid manager identifiers

**Test Cases:**

```python
- test_manager_group_initialization()
- test_manager_group_str_representation()
- test_manager_groups_list_not_empty()
- test_manager_groups_all_have_valid_priority()
- test_manager_groups_all_have_valid_names()
- test_manager_groups_all_have_valid_manager_lists()
- test_manager_group_priority_range()
```

### Tier 2: Very Low Coverage (< 50%)

#### 3. `src/cortex/rules/prompts_loader.py` (13.25% - 93/113 statements uncovered)

- **Impact**: +0.65% coverage if brought to 90%
- **Complexity**: Medium
- **Estimated Time**: 2-3 hours
- **Test File**: `tests/unit/test_prompts_loader.py` (NEW)

**What to Test:**

- `PromptsLoader.__init__()` with valid/invalid paths
- `load_manifest()` with existing/missing manifest
- `load_manifest()` with invalid JSON
- `get_categories()` with loaded/unloaded manifest
- `load_category()` with valid/invalid categories
- `load_category()` with missing prompt files
- `load_prompt()` with valid/invalid prompt names
- Error handling for file I/O failures
- Manifest caching behavior

**Test Cases:**

```python
- test_init_with_valid_path()
- test_init_with_invalid_path()
- test_load_manifest_success()
- test_load_manifest_missing_file()
- test_load_manifest_invalid_json()
- test_load_manifest_io_error()
- test_get_categories_with_manifest()
- test_get_categories_without_manifest()
- test_load_category_success()
- test_load_category_invalid_category()
- test_load_category_missing_files()
- test_load_prompt_success()
- test_load_prompt_invalid_name()
- test_load_prompt_missing_file()
- test_manifest_caching()
```

#### 4. `src/cortex/managers/container_factory.py` (43.92% - 83/148 statements uncovered)

- **Impact**: +0.35% coverage if brought to 90%
- **Complexity**: High
- **Estimated Time**: 4-5 hours
- **Test File**: `tests/unit/test_container_factory.py` (NEW)

**What to Test:**

- `create_foundation_managers()` with valid project root
- `create_linking_managers_from_foundation()` with valid foundation managers
- `create_optimization_managers_from_deps()` with valid dependencies
- `create_analysis_managers_from_deps()` with valid dependencies
- `create_refactoring_managers_from_optimization()` with valid optimization managers
- `create_execution_managers_from_deps()` with valid dependencies
- `create_all_managers()` integration test
- Error handling for invalid project roots
- Manager dependency injection correctness

**Test Cases:**

```python
- test_create_foundation_managers_success()
- test_create_foundation_managers_invalid_root()
- test_create_linking_managers_from_foundation()
- test_create_optimization_managers_from_deps()
- test_create_analysis_managers_from_deps()
- test_create_refactoring_managers_from_optimization()
- test_create_execution_managers_from_deps()
- test_create_all_managers_integration()
- test_manager_dependency_injection()
- test_error_handling_invalid_dependencies()
```

#### 5. `src/cortex/optimization/rules_manager.py` (49.56% - 80/176 statements uncovered)

- **Impact**: +0.30% coverage if brought to 90%
- **Complexity**: Medium-High
- **Estimated Time**: 3-4 hours
- **Test File**: `tests/unit/test_rules_manager.py` (EXISTS - needs expansion)

**What to Test:**

- Additional edge cases for rule merging
- Synapse manager integration
- Rule indexing with various configurations
- Error handling for missing rule files
- Context detection edge cases
- Rule filtering by category

**Test Cases:**

```python
- test_merge_rules_with_synapse_manager()
- test_index_rules_with_custom_config()
- test_load_rules_missing_files()
- test_context_detection_edge_cases()
- test_filter_rules_by_category()
- test_rule_priority_handling()
```

### Tier 3: Low Coverage (50-80%)

#### 6. `src/cortex/tools/synapse_tools.py` (69.54% - 33/121 statements uncovered)

- **Impact**: +0.18% coverage if brought to 90%
- **Complexity**: Medium
- **Estimated Time**: 2-3 hours
- **Test File**: `tests/tools/test_synapse_tools.py` (EXISTS - needs expansion)

**What to Test:**

- Additional MCP tool edge cases
- Error handling for git operations
- Submodule validation
- Rule/prompt update operations
- Sync operations with conflicts

#### 7. `src/cortex/structure/lifecycle/symlinks.py` (72.18% - 21/101 statements uncovered)

- **Impact**: +0.15% coverage if brought to 90%
- **Complexity**: Medium
- **Estimated Time**: 2-3 hours
- **Test File**: `tests/unit/test_symlinks.py` (NEW)

**What to Test:**

- Symlink creation on various platforms
- Symlink validation
- Broken symlink detection
- Symlink repair operations
- Error handling for permission issues

#### 8. `src/cortex/rules/synapse_repository.py` (77.07% - 26/123 statements uncovered)

- **Impact**: +0.11% coverage if brought to 90%
- **Complexity**: Medium
- **Estimated Time**: 2-3 hours
- **Test File**: `tests/unit/test_synapse_repository.py` (EXISTS - needs expansion)

**What to Test:**

- Git submodule operations
- Repository sync with conflicts
- Error handling for git failures
- Branch management
- Remote operations

#### 9. `src/cortex/rules/synapse_manager.py` (76.35% - 26/128 statements uncovered)

- **Impact**: +0.11% coverage if brought to 90%
- **Complexity**: Medium
- **Estimated Time**: 2-3 hours
- **Test File**: `tests/unit/test_synapse_manager.py` (EXISTS - needs expansion)

**What to Test:**

- Manager initialization edge cases
- Rule loading with various configurations
- Error recovery scenarios
- Cache invalidation
- Lazy loading behavior

## Implementation Strategy

### Phase 1: Quick Wins (Tier 1) - Target: +0.18% coverage

1. Create `test_resources.py` - 30 minutes
2. Create `test_manager_groups.py` - 30 minutes
3. **Expected Result**: 88.70% coverage

### Phase 2: Medium Effort (Tier 2 Priority) - Target: +0.65% coverage

1. Create `test_prompts_loader.py` - 2-3 hours
2. **Expected Result**: 89.35% coverage

### Phase 3: High Impact (Tier 2 Remaining) - Target: +0.65% coverage

1. Create `test_container_factory.py` - 4-5 hours
2. Expand `test_rules_manager.py` - 3-4 hours
3. **Expected Result**: 90.00%+ coverage

### Phase 4: Polish (Tier 3) - Target: +0.55% coverage buffer

1. Expand existing test files for Tier 3 modules
2. **Expected Result**: 90.55%+ coverage (buffer above threshold)

## Success Criteria

- ✅ Overall test coverage ≥ 90.00%
- ✅ All new test files follow AAA pattern (Arrange-Act-Assert)
- ✅ All tests pass with 100% pass rate
- ✅ No test skips without justification
- ✅ All tests complete in < 10 seconds
- ✅ Test coverage for each module ≥ 90% (where feasible)

## Estimated Timeline

- **Phase 1**: 1 hour
- **Phase 2**: 2-3 hours
- **Phase 3**: 7-9 hours
- **Phase 4**: 6-9 hours (optional, for buffer)

**Total**: 16-22 hours (2-3 days of focused work)

## Notes

- Focus on Phase 1 and Phase 2 first to reach 90% threshold quickly
- Phase 3 ensures we have a solid buffer above 90%
- Phase 4 is optional but recommended for long-term maintainability
- All tests must follow project testing standards (AAA pattern, no blanket skips)
- Use existing test patterns from similar modules as reference

## Dependencies

- Existing test infrastructure
- Mock libraries for file I/O and git operations
- Temporary directory fixtures for integration tests

## Risk Mitigation

- Start with simplest modules (resources.py, manager_groups.py) to build momentum
- Use existing test files as templates for structure and patterns
- Test incrementally - verify coverage after each module
- Keep tests focused and maintainable
