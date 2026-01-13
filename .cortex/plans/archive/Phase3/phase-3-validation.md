# Phase 3: Validation and Quality Checks

**Status:** Not Started
**Dependencies:** Phase 1 ✅ Complete, Phase 2 ✅ Complete
**Estimated Effort:** 4-6 hours implementation + 2-3 hours testing

---

## Overview

Phase 3 introduces automated validation and quality checks to ensure Memory Bank integrity, consistency, and adherence to best practices. This phase builds on Phase 1's metadata tracking and Phase 2's link analysis to provide comprehensive data quality assurance.

---

## Goals

### Primary Goals

1. **Schema Validation**: Enforce required sections per file type
2. **Duplication Detection**: Find and report duplicate content across files
3. **Token Budget Enforcement**: Hard limits with warnings before reaching limits
4. **Link Integrity**: Comprehensive link validation (building on Phase 2)
5. **Quality Metrics**: Scoring system for Memory Bank health

### Secondary Goals

1. **Automated Validation**: Run checks on write operations
2. **Validation Reports**: Human-readable reports with actionable suggestions
3. **Configuration**: User-configurable validation rules
4. **CI/CD Integration**: Validation as pre-commit hook

---

## Architecture

### New Modules (4 modules)

```text
src/cortex/
├── schema_validator.py        (~300 lines) - Enforce file schemas
├── duplication_detector.py    (~250 lines) - Find duplicate content
├── quality_metrics.py         (~200 lines) - Calculate quality scores
└── validation_config.py       (~150 lines) - User configuration
```

### Enhanced Modules

```text
src/cortex/
├── main.py                    (+250 lines) - 5 new MCP tools
└── metadata_index.py          (+100 lines) - Track validation results
```

---

## Implementation Plan

### Module 1: Schema Validator (`schema_validator.py`)

**Purpose:** Enforce required sections and structure per file type

#### Schema Validator Features

- Define schemas for each Memory Bank file type
- Validate required sections exist
- Check section order (optional)
- Validate heading levels and hierarchy
- Check for required content patterns
- Allow user-defined custom schemas

#### Schema Validator API Design

```python
class SchemaValidator:
    """Validate Memory Bank files against defined schemas."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize schema validator.

        Args:
            config_path: Optional path to custom schema config
        """
        self.schemas = self._load_default_schemas()
        if config_path:
            self.schemas.update(self._load_custom_schemas(config_path))

    async def validate_file(
        self,
        file_name: str,
        content: str,
        file_type: Optional[str] = None
    ) -> Dict:
        """
        Validate file against schema.

        Args:
            file_name: Name of file
            content: File content
            file_type: Optional file type override

        Returns:
            {
                "valid": bool,
                "errors": [
                    {
                        "type": "missing_section",
                        "severity": "error",
                        "message": "Required section 'Goals' not found",
                        "suggestion": "Add ## Goals section"
                    }
                ],
                "warnings": [...],
                "score": 85  # 0-100
            }
        """

    def get_schema(self, file_name: str) -> Dict:
        """Get schema definition for file."""

    def _load_default_schemas(self) -> Dict:
        """Load built-in schemas."""

    def _load_custom_schemas(self, config_path: Path) -> Dict:
        """Load user-defined schemas."""

    def _check_required_sections(
        self,
        sections: List[str],
        required: List[str]
    ) -> List[Dict]:
        """Check if required sections are present."""

    def _check_section_order(
        self,
        sections: List[str],
        expected_order: List[str]
    ) -> List[Dict]:
        """Check if sections follow expected order."""

    def _check_heading_levels(self, content: str) -> List[Dict]:
        """Check for proper heading hierarchy (no skipped levels)."""
```

#### Default Schemas

```python
DEFAULT_SCHEMAS = {
    "projectBrief.md": {
        "required_sections": [
            "Project Overview",
            "Goals",
            "Core Requirements",
            "Success Criteria"
        ],
        "recommended_sections": [
            "Constraints",
            "Key Decisions"
        ],
        "heading_level": 2,  # Must start with ##
        "max_nesting": 3,    # Max ### depth
    },
    "activeContext.md": {
        "required_sections": [
            "Current Focus",
            "Recent Changes",
            "Next Steps"
        ],
        "recommended_sections": [
            "Active Decisions",
            "Important Patterns"
        ],
        "heading_level": 2,
    },
    "systemPatterns.md": {
        "required_sections": [
            "Architecture",
            "Design Patterns",
            "Component Relationships"
        ],
        "heading_level": 2,
    },
    # ... schemas for all 7 files
}
```

---

### Module 2: Duplication Detector (`duplication_detector.py`)

**Purpose:** Find and report duplicate or highly similar content

#### Duplication Detector Features

- Content hash comparison (from Phase 1)
- Fuzzy text similarity detection
- Section-level comparison
- Cross-file duplication detection
- Configurable similarity threshold
- Smart suggestions for refactoring duplicates

#### Duplication Detector API Design

```python
class DuplicationDetector:
    """Detect duplicate content across Memory Bank files."""

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        min_content_length: int = 50
    ):
        """
        Initialize duplication detector.

        Args:
            similarity_threshold: Similarity score 0.0-1.0 to flag as duplicate
            min_content_length: Minimum chars to check for duplication
        """
        self.threshold = similarity_threshold
        self.min_length = min_content_length

    async def scan_all_files(
        self,
        memory_bank_dir: Path,
        file_system: FileSystemManager
    ) -> Dict:
        """
        Scan all files for duplications.

        Returns:
            {
                "duplicates_found": 5,
                "duplications": [
                    {
                        "file1": "projectBrief.md",
                        "section1": "Goals",
                        "file2": "productContext.md",
                        "section2": "Project Goals",
                        "similarity": 0.95,
                        "suggestion": "Use transclusion: {{include: projectBrief.md#Goals}}"
                    }
                ],
                "exact_duplicates": [...],
                "similar_content": [...]
            }
        """

    def compare_sections(
        self,
        content1: str,
        content2: str
    ) -> float:
        """
        Calculate similarity score between two content blocks.

        Returns:
            Similarity score 0.0-1.0
        """

    def find_exact_duplicates(
        self,
        files_content: Dict[str, str]
    ) -> List[Dict]:
        """Find sections with identical content hashes."""

    def find_similar_content(
        self,
        files_content: Dict[str, str]
    ) -> List[Dict]:
        """Find sections with high similarity scores."""

    def generate_refactoring_suggestion(
        self,
        duplication: Dict
    ) -> str:
        """Generate suggestion for eliminating duplication."""

    def _calculate_similarity(
        self,
        text1: str,
        text2: str
    ) -> float:
        """Calculate text similarity using multiple algorithms."""
```

#### Similarity Algorithms

```python
def _calculate_similarity(self, text1: str, text2: str) -> float:
    """
    Use multiple algorithms and average scores:
    1. Levenshtein distance (character-level)
    2. Token-based Jaccard similarity
    3. Cosine similarity (TF-IDF vectors)
    """
    scores = []

    # Levenshtein
    scores.append(self._levenshtein_similarity(text1, text2))

    # Jaccard (token sets)
    scores.append(self._jaccard_similarity(text1, text2))

    # Cosine (TF-IDF)
    scores.append(self._cosine_similarity(text1, text2))

    return sum(scores) / len(scores)
```

---

### Module 3: Quality Metrics (`quality_metrics.py`)

**Purpose:** Calculate overall Memory Bank health scores

#### Quality Metrics Features

- Overall quality score (0-100)
- Per-file quality scores
- Metric categories (completeness, consistency, freshness)
- Trend tracking over time
- Quality thresholds with alerts

#### Quality Metrics API Design

```python
class QualityMetrics:
    """Calculate Memory Bank quality metrics."""

    def __init__(self, metadata_index: MetadataIndex):
        """Initialize with metadata index access."""
        self.index = metadata_index

    async def calculate_overall_score(
        self,
        memory_bank_dir: Path
    ) -> Dict:
        """
        Calculate overall Memory Bank quality score.

        Returns:
            {
                "overall_score": 87,  # 0-100
                "breakdown": {
                    "completeness": 90,    # All required sections present
                    "consistency": 85,     # Low duplication, good links
                    "freshness": 88,       # Recently updated
                    "structure": 90,       # Good organization
                    "token_efficiency": 82 # Within budget, no bloat
                },
                "grade": "A",  # A, B, C, D, F
                "status": "healthy",
                "issues": [
                    "2 files have missing required sections",
                    "3 duplicate sections found"
                ],
                "recommendations": [...]
            }
        """

    async def calculate_file_score(
        self,
        file_name: str,
        content: str,
        metadata: Dict
    ) -> Dict:
        """Calculate quality score for individual file."""

    def _calculate_completeness(
        self,
        file_name: str,
        content: str
    ) -> float:
        """Score based on required sections present."""

    def _calculate_consistency(
        self,
        file_name: str,
        duplication_data: Dict
    ) -> float:
        """Score based on duplication and link integrity."""

    def _calculate_freshness(
        self,
        metadata: Dict
    ) -> float:
        """Score based on last modified time."""

    def _calculate_structure(
        self,
        content: str
    ) -> float:
        """Score based on heading hierarchy and organization."""

    def _calculate_token_efficiency(
        self,
        token_count: int,
        file_size: int
    ) -> float:
        """Score based on token/size ratio and budget usage."""

    def get_grade(self, score: float) -> str:
        """Convert score to letter grade."""
        # A: 90-100, B: 80-89, C: 70-79, D: 60-69, F: <60
```

---

### Module 4: Validation Config (`validation_config.py`)

**Purpose:** User-configurable validation rules

#### Validation Config Features

- Load config from `.memory-bank-validation.json`
- Default config with sensible defaults
- Per-file type configuration
- Global validation settings
- Schema customization

#### Validation Config API Design

```python
class ValidationConfig:
    """Manage validation configuration."""

    def __init__(self, project_root: Path):
        """Initialize with project root."""
        self.project_root = project_root
        self.config_path = project_root / ".memory-bank-validation.json"
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """
        Load validation config.

        Default config structure:
        {
            "enabled": true,
            "auto_validate_on_write": true,
            "strict_mode": false,
            "token_budget": {
                "max_total_tokens": 100000,
                "warn_at_percentage": 80,
                "per_file_max": 15000
            },
            "duplication": {
                "enabled": true,
                "threshold": 0.85,
                "min_length": 50
            },
            "schemas": {
                "enforce_required_sections": true,
                "enforce_section_order": false,
                "custom_schemas": {}
            },
            "quality": {
                "minimum_score": 70,
                "fail_below": 50
            }
        }
        """

    def get(self, key: str, default=None):
        """Get config value with dot notation."""

    def set(self, key: str, value):
        """Set config value."""

    async def save(self):
        """Save config to file."""

    def reset_to_defaults(self):
        """Reset to default configuration."""

    def validate_config(self) -> List[str]:
        """Validate config structure and return errors."""
```

---

### Module 5: Update Main.py (New MCP Tools)

#### New MCP Tools for Validation (5 tools)

#### 1. `validate_memory_bank()`

```python
@mcp.tool()
async def validate_memory_bank(
    file_name: str = None,
    project_root: str = None,
    strict: bool = False
) -> str:
    """
    Run comprehensive validation on Memory Bank.

    Args:
        file_name: Optional specific file (if None, validates all)
        project_root: Optional project root
        strict: Enable strict validation (fail on warnings)

    Returns:
        Validation report with errors, warnings, and suggestions
    """
```

#### 2. `check_duplications()`

```python
@mcp.tool()
async def check_duplications(
    project_root: str = None,
    threshold: float = 0.85,
    suggest_fixes: bool = True
) -> str:
    """
    Find duplicate content across files.

    Returns:
        Report of duplications with refactoring suggestions
    """
```

#### 3. `get_quality_score()`

```python
@mcp.tool()
async def get_quality_score(
    project_root: str = None,
    detailed: bool = True
) -> str:
    """
    Calculate Memory Bank quality score.

    Returns:
        Overall score, breakdown by category, and recommendations
    """
```

#### 4. `check_token_budget()`

```python
@mcp.tool()
async def check_token_budget(
    project_root: str = None,
    include_projections: bool = True
) -> str:
    """
    Check token usage against budget.

    Returns:
        Current usage, remaining budget, and projections
    """
```

#### 5. `configure_validation()`

```python
@mcp.tool()
async def configure_validation(
    project_root: str = None,
    config_key: str = None,
    config_value: str = None,
    show_current: bool = False
) -> str:
    """
    View or update validation configuration.

    Returns:
        Current or updated configuration
    """
```

---

## Validation Rules

### Schema Validation Rules

**projectBrief.md:**

- ✅ MUST have: Project Overview, Goals, Core Requirements, Success Criteria
- ⚠️ SHOULD have: Constraints, Key Decisions
- ✅ Headings MUST be level 2 (##)
- ✅ NO heading level skips (## -> #### invalid)

**activeContext.md:**

- ✅ MUST have: Current Focus, Recent Changes, Next Steps
- ⚠️ SHOULD have: Active Decisions, Important Patterns
- ⚠️ Recent Changes SHOULD have entries from last 7 days

**systemPatterns.md:**

- ✅ MUST have: Architecture, Design Patterns
- ⚠️ SHOULD have: Component Relationships, Critical Paths

**progress.md:**

- ✅ MUST have: What Works, What's Left
- ⚠️ SHOULD be updated within last 7 days

### Token Budget Rules

```python
TOKEN_BUDGET_RULES = {
    "max_total_tokens": 100_000,      # Hard limit for all files
    "warn_at_percentage": 80,          # Warn at 80% usage
    "per_file_max": 15_000,           # Max tokens per file
    "per_file_warn": 12_000,          # Warn per file
    "emergency_threshold": 95,         # Critical alert
}
```

### Duplication Rules

- Exact duplicates (100% match): **ERROR**
- High similarity (>90%): **WARNING** with transclusion suggestion
- Medium similarity (85-90%): **INFO** with review suggestion
- Low similarity (<85%): Ignored

---

## Testing Strategy

### Unit Tests

1. **Schema Validator Tests**
   - Validate files with all required sections
   - Detect missing required sections
   - Check heading levels
   - Validate custom schemas
   - Test section order enforcement

2. **Duplication Detector Tests**
   - Find exact duplicates
   - Detect similar content (various thresholds)
   - Generate refactoring suggestions
   - Test similarity algorithms

3. **Quality Metrics Tests**
   - Calculate overall score
   - Calculate per-category scores
   - Test grade assignment
   - Trend tracking

4. **Validation Config Tests**
   - Load default config
   - Load custom config
   - Validate config structure
   - Save config changes

### Integration Tests

1. End-to-end validation workflow
2. Validation on write operations
3. Quality score calculation with real data
4. Configuration persistence

### Edge Cases

- Empty files
- Files with only headings
- Very large files (token limit)
- Multiple levels of duplication
- Circular references in suggestions
- Invalid config files

---

## Configuration File Example

`.memory-bank-validation.json`:

```json
{
  "enabled": true,
  "auto_validate_on_write": true,
  "strict_mode": false,

  "token_budget": {
    "max_total_tokens": 100000,
    "warn_at_percentage": 80,
    "per_file_max": 15000
  },

  "duplication": {
    "enabled": true,
    "threshold": 0.85,
    "min_length": 50,
    "suggest_transclusion": true
  },

  "schemas": {
    "enforce_required_sections": true,
    "enforce_section_order": false,
    "custom_schemas": {
      "projectBrief.md": {
        "required_sections": ["Project Overview", "Goals"],
        "recommended_sections": ["Constraints"]
      }
    }
  },

  "quality": {
    "minimum_score": 70,
    "fail_below": 50,
    "weights": {
      "completeness": 0.25,
      "consistency": 0.25,
      "freshness": 0.15,
      "structure": 0.20,
      "token_efficiency": 0.15
    }
  }
}
```

---

## Success Criteria

Phase 3 is complete when:

✅ **Schema Validator**

- Validates all 7 Memory Bank files
- Detects missing required sections
- Checks heading hierarchy
- Supports custom schemas

✅ **Duplication Detector**

- Finds exact duplicates
- Detects similar content (configurable threshold)
- Generates refactoring suggestions
- Suggests transclusions for duplicates

✅ **Quality Metrics**

- Calculates overall quality score
- Provides category breakdown
- Assigns letter grade
- Tracks trends over time

✅ **Validation Config**

- Loads and saves configuration
- Supports custom validation rules
- Validates config structure

✅ **MCP Tools**

- All 5 tools implemented
- All tools tested
- Documentation complete

✅ **Testing**

- Unit tests: >90% coverage
- Integration tests passing
- Edge cases handled

✅ **Auto-validation**

- Runs on write operations (if enabled)
- Provides immediate feedback
- Doesn't break write flow

---

## Integration Points

### Phase 1 Integration

- Use MetadataIndex for file metadata
- Use FileSystemManager for file I/O
- Use TokenCounter for token tracking
- Use content hashes for exact duplicate detection

### Phase 2 Integration

- Use LinkValidator for link integrity
- Suggest transclusions for duplicates
- Validate transclusion syntax
- Check for broken transclusions

### Future Phases

- Phase 4: Use validation data for optimization decisions
- Phase 5: Use quality scores for AI refactoring priorities

---

## Timeline Estimate

### Implementation (4-6 hours)

- Schema Validator: 1.5 hours
- Duplication Detector: 1.5 hours
- Quality Metrics: 1 hour
- Validation Config: 0.5 hours
- MCP Tools: 1 hour
- Integration: 0.5 hours

### Testing (2-3 hours)

- Unit tests: 1.5 hours
- Integration tests: 1 hour
- Edge case testing: 0.5 hours

### Documentation (1 hour)

- User guides: 0.5 hours
- API docs: 0.5 hours

#### Total: 7-10 hours

---

## Risks and Mitigation

### Risk 1: False Positives in Duplication

**Risk**: Similarity detection flags legitimate different content
**Mitigation**:

- Configurable threshold
- Multiple similarity algorithms (averaged)
- Min content length filter
- User feedback loop to tune thresholds

### Risk 2: Performance Impact

**Risk**: Validation slows down write operations
**Mitigation**:

- Make auto-validation optional
- Async validation (non-blocking)
- Incremental validation (only changed files)
- Cache validation results

### Risk 3: Schema Rigidity

**Risk**: Strict schemas prevent valid use cases
**Mitigation**:

- Warnings vs errors (configurable)
- Custom schema support
- Easy config override
- "Strict mode" optional

### Risk 4: Token Budget Conflicts

**Risk**: Budget limits block legitimate writes
**Mitigation**:

- Warnings before hard limits
- Emergency override option
- Gradual approach to limit
- Suggestions for reducing tokens

---

## Future Enhancements (Phase 4+)

### Beyond Phase 3

1. **AI-Powered Validation**
   - Semantic similarity detection
   - Content quality assessment
   - Automatic fix suggestions

2. **Advanced Metrics**
   - Complexity scoring
   - Readability metrics
   - Cross-reference density

3. **Automated Fixes**
   - Auto-fix formatting issues
   - Auto-create missing sections (templates)
   - Auto-refactor duplications

4. **Validation Dashboard**
   - Web-based validation reports
   - Historical quality trends
   - Team quality leaderboard

5. **Pre-commit Hooks**
   - Git hook integration
   - CI/CD pipeline validation
   - Block commits below quality threshold

---

**Last Updated:** December 19, 2025
**Status:** Ready for implementation
**Dependencies:** Phase 1 ✅ Complete, Phase 2 ✅ Complete
