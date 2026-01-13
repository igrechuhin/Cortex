# Phase 4: Token Optimization

**Status:** Not Started
**Dependencies:** Phase 1 ✅ Complete, Phase 2 ✅ Complete, Phase 3 ✅ Complete
**Estimated Effort:** 6-8 hours implementation + 3-4 hours testing

---

## Overview

Phase 4 introduces intelligent token optimization to minimize token usage while maintaining context quality. This phase builds on Phase 1's token counting, Phase 2's dependency graphs, and Phase 3's quality metrics to provide smart context selection and progressive loading strategies.

---

## Goals

### Primary Goals

1. **Smart Context Selection**: Intelligently choose which files/sections to include based on task description
2. **Progressive Loading**: Load context incrementally based on priority and relevance
3. **Automatic Summarization**: Generate summaries of old or less relevant content
4. **Context Budget Management**: Stay within token limits while maximizing information value
5. **Relevance Scoring**: Score files and sections by relevance to current task

### Secondary Goals

1. **Context Templates**: Pre-configured loading strategies for common tasks
2. **Historical Usage Tracking**: Learn from past context usage patterns
3. **Compression Strategies**: Identify opportunities to compress verbose content
4. **Cache Optimization**: Smart caching of frequently accessed contexts
5. **Performance Monitoring**: Track token efficiency over time

---

## Architecture

### New Modules (5 modules)

```text
src/cortex/
├── context_optimizer.py       (~400 lines) - Smart context selection
├── progressive_loader.py      (~350 lines) - Incremental loading strategies
├── summarization_engine.py    (~300 lines) - Content summarization
├── relevance_scorer.py        (~250 lines) - Score content relevance
└── optimization_config.py     (~150 lines) - Optimization configuration
```

### Enhanced Modules

```text
src/cortex/
├── main.py                    (+400 lines) - 5 new MCP tools
└── metadata_index.py          (+100 lines) - Track usage statistics
```

---

## Implementation Plan

### Module 1: Relevance Scorer (`relevance_scorer.py`)

**Purpose:** Score files and sections by relevance to a given task description

#### Features

- Keyword matching and TF-IDF scoring
- Semantic similarity (if embedding support added)
- Dependency-based relevance (files that are dependencies score higher)
- Recency weighting (recently modified files score higher)
- Manual priority overrides from metadata

#### API Design

```python
class RelevanceScorer:
    """Score content relevance for context selection."""

    def __init__(
        self,
        dependency_graph: DependencyGraph,
        metadata_index: MetadataIndex
    ):
        """
        Initialize relevance scorer.

        Args:
            dependency_graph: Dependency graph for relationship analysis
            metadata_index: Metadata index for file information
        """
        self.dependency_graph = dependency_graph
        self.metadata_index = metadata_index

    async def score_files(
        self,
        task_description: str,
        files_content: Dict[str, str],
        files_metadata: Dict[str, Dict]
    ) -> Dict[str, float]:
        """
        Score files by relevance to task.

        Args:
            task_description: Description of the task
            files_content: Dict mapping file names to content
            files_metadata: Dict mapping file names to metadata

        Returns:
            {
                "file_name": 0.85,  # relevance score 0.0-1.0
                ...
            }
        """

    async def score_sections(
        self,
        task_description: str,
        file_name: str,
        content: str
    ) -> List[Dict]:
        """
        Score sections within a file.

        Returns:
            [
                {
                    "section": "Goals",
                    "score": 0.90,
                    "reason": "Contains keywords: 'build', 'system'"
                }
            ]
        """

    def _calculate_keyword_score(
        self,
        task_description: str,
        content: str
    ) -> float:
        """Calculate TF-IDF based keyword score."""

    def _calculate_dependency_score(
        self,
        file_name: str,
        scored_files: Dict[str, float]
    ) -> float:
        """Boost score based on dependencies of high-scoring files."""

    def _calculate_recency_score(
        self,
        metadata: Dict
    ) -> float:
        """Score based on how recently the file was modified."""

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords from text."""
```

---

### Module 2: Context Optimizer (`context_optimizer.py`)

**Purpose:** Select optimal subset of content to fit within token budget

#### Context Optimizer Features

- Multiple optimization strategies (greedy, priority-based, dependency-aware)
- Token budget enforcement
- Mandatory file inclusion (e.g., always include memorybankinstructions.md)
- Section-level granularity (include high-value sections from lower-scored files)
- Quality-aware optimization (prefer higher quality content)

#### Context Optimizer API Design

```python
class ContextOptimizer:
    """Optimize context selection within token budget."""

    def __init__(
        self,
        token_counter: TokenCounter,
        relevance_scorer: RelevanceScorer,
        quality_metrics: QualityMetrics
    ):
        """Initialize context optimizer."""
        self.token_counter = token_counter
        self.relevance_scorer = relevance_scorer
        self.quality_metrics = quality_metrics

    async def optimize_context(
        self,
        task_description: str,
        files_content: Dict[str, str],
        files_metadata: Dict[str, Dict],
        token_budget: int,
        strategy: str = "dependency_aware"
    ) -> Dict:
        """
        Select optimal context within budget.

        Args:
            task_description: Description of task
            files_content: Available files
            files_metadata: File metadata
            token_budget: Maximum tokens allowed
            strategy: Optimization strategy

        Returns:
            {
                "selected_files": ["file1.md", "file2.md"],
                "selected_sections": {
                    "file3.md": ["Goals", "Requirements"]
                },
                "total_tokens": 45000,
                "utilization": 0.90,  # 90% of budget
                "excluded_files": ["file4.md"],
                "strategy_used": "dependency_aware"
            }
        """

    async def optimize_by_priority(
        self,
        relevance_scores: Dict[str, float],
        files_content: Dict[str, str],
        token_budget: int
    ) -> List[str]:
        """
        Greedy optimization: select highest-scoring files first.
        """

    async def optimize_by_dependencies(
        self,
        relevance_scores: Dict[str, float],
        files_content: Dict[str, str],
        token_budget: int
    ) -> List[str]:
        """
        Dependency-aware: ensure all dependencies of included files are also included.
        """

    async def optimize_with_sections(
        self,
        relevance_scores: Dict[str, float],
        files_content: Dict[str, str],
        token_budget: int
    ) -> Dict:
        """
        Section-level optimization: include partial files when beneficial.
        """

    def _must_include_files(self) -> List[str]:
        """Return list of files that must always be included."""
        return ["memorybankinstructions.md"]
```

---

### Module 3: Progressive Loader (`progressive_loader.py`)

**Purpose:** Load context incrementally based on priority and budget

#### Progressive Loader Features

- Multiple loading strategies
  - By priority (foundation → context → active)
  - By dependency chain (load dependencies first)
  - By token budget (stop at limit)
  - By recency (recently changed first)
- Lazy loading (load on demand)
- Streaming support (return partial results)
- Checkpointing (resume from where you left off)

#### Progressive Loader API Design

```python
class ProgressiveLoader:
    """Load context progressively based on strategy."""

    def __init__(
        self,
        file_system: FileSystemManager,
        context_optimizer: ContextOptimizer,
        metadata_index: MetadataIndex
    ):
        """Initialize progressive loader."""
        self.file_system = file_system
        self.context_optimizer = context_optimizer
        self.metadata_index = metadata_index

    async def load_by_priority(
        self,
        task_description: str,
        token_budget: int,
        priority_order: List[str] = None
    ) -> AsyncIterator[Dict]:
        """
        Load files in priority order.

        Yields:
            {
                "file_name": "projectBrief.md",
                "content": "...",
                "tokens": 5000,
                "cumulative_tokens": 5000,
                "priority": 1,
                "more_available": True
            }
        """

    async def load_by_dependencies(
        self,
        entry_files: List[str],
        token_budget: int
    ) -> AsyncIterator[Dict]:
        """
        Load dependency chain starting from entry files.
        """

    async def load_by_relevance(
        self,
        task_description: str,
        token_budget: int
    ) -> AsyncIterator[Dict]:
        """
        Load most relevant files first.
        """

    async def load_with_budget(
        self,
        files: List[str],
        token_budget: int,
        stop_at_budget: bool = True
    ) -> List[Dict]:
        """
        Load files until budget is reached.
        """

    def get_default_priority_order(self) -> List[str]:
        """
        Get default file priority order.

        Returns:
            ["memorybankinstructions.md", "projectBrief.md", ...]
        """
```

---

### Module 4: Summarization Engine (`summarization_engine.py`)

**Purpose:** Generate summaries of content to reduce token usage

#### Summarization Engine Features

- Multiple summarization strategies
  - Extract key sections only
  - Generate brief summaries (using LLM if available)
  - Remove verbose examples
  - Compress repeated information
- Configurable compression ratio
- Quality preservation (ensure summaries are useful)
- Caching of generated summaries

#### Summarization Engine API Design

```python
class SummarizationEngine:
    """Generate summaries to reduce token usage."""

    def __init__(
        self,
        token_counter: TokenCounter,
        metadata_index: MetadataIndex
    ):
        """Initialize summarization engine."""
        self.token_counter = token_counter
        self.metadata_index = metadata_index

    async def summarize_file(
        self,
        file_name: str,
        content: str,
        target_reduction: float = 0.5,
        strategy: str = "extract_key_sections"
    ) -> Dict:
        """
        Summarize file content.

        Args:
            file_name: Name of file
            content: File content
            target_reduction: Target token reduction (0.5 = reduce by 50%)
            strategy: Summarization strategy

        Returns:
            {
                "original_tokens": 10000,
                "summarized_tokens": 5000,
                "reduction": 0.50,
                "summary": "...",
                "strategy_used": "extract_key_sections"
            }
        """

    async def extract_key_sections(
        self,
        content: str,
        target_tokens: int
    ) -> str:
        """
        Extract only the most important sections.
        """

    async def compress_verbose_content(
        self,
        content: str,
        target_reduction: float
    ) -> str:
        """
        Remove verbose examples and compress repeated info.
        """

    async def generate_brief_summary(
        self,
        content: str,
        max_tokens: int
    ) -> str:
        """
        Generate a brief summary of the content.
        Note: Requires LLM integration (future enhancement).
        """

    def _identify_verbose_sections(self, content: str) -> List[Dict]:
        """Identify sections that are candidates for compression."""

    def _cache_summary(
        self,
        file_name: str,
        content_hash: str,
        summary: str
    ):
        """Cache generated summary."""

    def _get_cached_summary(
        self,
        file_name: str,
        content_hash: str
    ) -> Optional[str]:
        """Get cached summary if available."""
```

---

### Module 5: Optimization Config (`optimization_config.py`)

**Purpose:** Manage optimization configuration

#### Optimization Config Features

- JSON-based configuration
- Token budget settings
- Loading strategies and priorities
- Summarization preferences
- Performance targets

#### Optimization Config API Design

```python
DEFAULT_OPTIMIZATION_CONFIG = {
    "enabled": True,
    "token_budget": {
        "default_budget": 80000,
        "max_budget": 100000,
        "reserve_for_response": 10000
    },
    "loading_strategy": {
        "default": "dependency_aware",
        "mandatory_files": ["memorybankinstructions.md"],
        "priority_order": [
            "memorybankinstructions.md",
            "projectBrief.md",
            "activeContext.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
            "progress.md"
        ]
    },
    "summarization": {
        "enabled": True,
        "auto_summarize_old_files": True,
        "age_threshold_days": 90,
        "target_reduction": 0.5,
        "strategy": "extract_key_sections"
    },
    "relevance": {
        "keyword_weight": 0.4,
        "dependency_weight": 0.3,
        "recency_weight": 0.2,
        "quality_weight": 0.1
    }
}

class OptimizationConfig:
    """Manage optimization configuration."""

    def __init__(self, project_root: Path):
        """Initialize with project root."""
        self.project_root = project_root
        self.config_path = project_root / ".memory-bank-optimization.json"
        self.config = self._load_config()

    # Similar API to ValidationConfig
```

---

### Module 6: Update Main.py (New MCP Tools)

#### New MCP Tools for Optimization (5 tools)

#### 1. `optimize_context()`

```python
@mcp.tool()
async def optimize_context(
    task_description: str,
    token_budget: int = None,
    strategy: str = "dependency_aware",
    project_root: str = None
) -> str:
    """
    Select optimal context for a task within token budget.

    Args:
        task_description: Description of the task
        token_budget: Max tokens (defaults to config)
        strategy: Optimization strategy
        project_root: Optional project root

    Returns:
        JSON with selected files and sections
    """
```

#### 2. `load_progressive_context()`

```python
@mcp.tool()
async def load_progressive_context(
    task_description: str,
    token_budget: int = None,
    loading_strategy: str = "by_relevance",
    project_root: str = None
) -> str:
    """
    Load context progressively based on strategy.

    Returns:
        JSON with loaded content in priority order
    """
```

#### 3. `summarize_content()`

```python
@mcp.tool()
async def summarize_content(
    file_name: str = None,
    target_reduction: float = 0.5,
    strategy: str = "extract_key_sections",
    project_root: str = None
) -> str:
    """
    Summarize Memory Bank content.

    Args:
        file_name: File to summarize (None for all)
        target_reduction: Target token reduction
        strategy: Summarization strategy

    Returns:
        JSON with summarized content
    """
```

#### 4. `get_relevance_scores()`

```python
@mcp.tool()
async def get_relevance_scores(
    task_description: str,
    project_root: str = None,
    include_sections: bool = False
) -> str:
    """
    Get relevance scores for all files.

    Returns:
        JSON with file and section relevance scores
    """
```

#### 5. `configure_optimization()`

```python
@mcp.tool()
async def configure_optimization(
    config_key: str = None,
    config_value: str = None,
    show_current: bool = False,
    project_root: str = None
) -> str:
    """
    View or update optimization configuration.

    Returns:
        JSON with current or updated configuration
    """
```

---

## Optimization Strategies

### Strategy 1: Priority-Based (Greedy)

- Sort files by relevance score
- Include files in order until budget reached
- Simple and fast
- May miss dependencies

### Strategy 2: Dependency-Aware

- Identify high-relevance files
- Include all their dependencies
- Ensures context completeness
- Better quality but may use more tokens

### Strategy 3: Section-Level

- Score individual sections
- Include high-value sections even from low-scored files
- Maximum efficiency
- More complex to implement

### Strategy 4: Hybrid

- Start with mandatory files
- Add high-relevance files with dependencies
- Fill remaining budget with high-value sections
- Best balance of quality and efficiency

---

## Testing Strategy

### Unit Tests

1. **Relevance Scorer Tests**
   - Keyword matching accuracy
   - Dependency-based scoring
   - Recency scoring
   - Score normalization

2. **Context Optimizer Tests**
   - Budget enforcement
   - Strategy selection
   - Mandatory file inclusion
   - Section-level optimization

3. **Progressive Loader Tests**
   - Loading strategies
   - Budget limits
   - Dependency ordering
   - Streaming support

4. **Summarization Engine Tests**
   - Content extraction
   - Token reduction accuracy
   - Summary quality
   - Cache functionality

5. **Optimization Config Tests**
   - Load/save configuration
   - Default values
   - Validation

### Integration Tests

1. End-to-end optimization workflow
2. Token budget enforcement across strategies
3. Quality preservation in summaries
4. Performance benchmarks

### Edge Cases

- Empty token budget
- Very small budgets (< 1000 tokens)
- All files exceed budget individually
- Circular dependencies in optimization
- Missing or corrupted files
- Invalid task descriptions

---

## Performance Targets

| Operation | Target | Stretch Goal |
|-----------|--------|--------------|
| Relevance scoring (all files) | <500ms | <200ms |
| Context optimization | <1s | <500ms |
| Progressive loading (per file) | <50ms | <20ms |
| Summarization (per file) | <2s | <1s |
| Cache hit rate | >80% | >90% |

---

## Success Criteria

Phase 4 is complete when:

✅ **Relevance Scorer**

- Scores files by keyword relevance
- Incorporates dependency relationships
- Weights by recency and quality
- Provides explainable scores

✅ **Context Optimizer**

- Selects optimal context within budget
- Supports multiple strategies
- Handles mandatory file inclusion
- Provides section-level optimization

✅ **Progressive Loader**

- Implements multiple loading strategies
- Streams results incrementally
- Respects token budgets
- Maintains loading state

✅ **Summarization Engine**

- Reduces token usage by target percentage
- Preserves key information
- Caches generated summaries
- Supports multiple strategies

✅ **MCP Tools**

- All 5 tools implemented and tested
- Documentation complete
- Performance targets met

✅ **Testing**

- Unit tests: >90% coverage
- Integration tests passing
- Performance benchmarks met
- Edge cases handled

---

## Integration Points

### Phase 1 Integration

- Use TokenCounter for accurate token tracking
- Use DependencyGraph for relationship analysis
- Use MetadataIndex for file statistics
- Use FileSystemManager for file I/O

### Phase 2 Integration

- Consider transclusion relationships in dependencies
- Validate links in optimized context
- Use link graph for relevance scoring

### Phase 3 Integration

- Use quality scores in optimization
- Respect validation rules
- Integrate with token budget configuration

### Future Phases

- Phase 5: Use optimization data for AI-driven refactoring

---

## Configuration File Example

`.memory-bank-optimization.json`:

```json
{
  "enabled": true,
  "token_budget": {
    "default_budget": 80000,
    "max_budget": 100000,
    "reserve_for_response": 10000
  },
  "loading_strategy": {
    "default": "dependency_aware",
    "mandatory_files": ["memorybankinstructions.md"],
    "priority_order": [
      "memorybankinstructions.md",
      "projectBrief.md",
      "activeContext.md",
      "systemPatterns.md",
      "techContext.md",
      "productContext.md",
      "progress.md"
    ]
  },
  "summarization": {
    "enabled": true,
    "auto_summarize_old_files": true,
    "age_threshold_days": 90,
    "target_reduction": 0.5,
    "strategy": "extract_key_sections",
    "cache_summaries": true
  },
  "relevance": {
    "keyword_weight": 0.4,
    "dependency_weight": 0.3,
    "recency_weight": 0.2,
    "quality_weight": 0.1
  },
  "performance": {
    "cache_enabled": true,
    "cache_ttl_seconds": 3600,
    "max_cache_size_mb": 50
  }
}
```

---

## Timeline Estimate

### Implementation (6-8 hours)

- Relevance Scorer: 1.5 hours
- Context Optimizer: 2 hours
- Progressive Loader: 1.5 hours
- Summarization Engine: 1.5 hours
- Optimization Config: 0.5 hours
- MCP Tools: 1 hour

### Testing (3-4 hours)

- Unit tests: 2 hours
- Integration tests: 1 hour
- Performance testing: 1 hour

### Documentation (1 hour)

- User guides: 0.5 hours
- API docs: 0.5 hours

#### Total: 10-13 hours

---

## Risks and Mitigation

### Risk 1: Relevance Scoring Accuracy

**Risk**: Simple keyword matching may not capture semantic relevance
**Mitigation**:

- Start with TF-IDF and keyword matching (proven, simple)
- Add dependency and recency signals
- Consider adding embeddings in future (Phase 5)
- Allow manual priority overrides

### Risk 2: Over-Optimization

**Risk**: Aggressive optimization may remove important context
**Mitigation**:

- Always include mandatory files
- Respect dependency relationships
- Test with real-world tasks
- Provide multiple strategies (conservative to aggressive)
- Add "safety margin" to budgets

### Risk 3: Performance Impact

**Risk**: Optimization overhead may slow down operations
**Mitigation**:

- Implement aggressive caching
- Make optimization opt-in
- Provide fast "greedy" strategy as default
- Benchmark and optimize hot paths

### Risk 4: Summarization Quality

**Risk**: Automated summarization may lose critical information
**Mitigation**:

- Start with conservative "extract key sections" strategy
- Require explicit user opt-in for aggressive summarization
- Cache summaries for review
- Provide "undo" capability
- Consider human-in-the-loop for important files

---

## Future Enhancements (Phase 5+)

### Beyond Phase 4

1. **Semantic Search**
   - Use embeddings for better relevance
   - Similarity-based context selection
   - Cross-file semantic relationships

2. **ML-Based Optimization**
   - Learn from usage patterns
   - Predict relevant files
   - Adaptive strategies

3. **LLM-Powered Summarization**
   - High-quality summaries using LLMs
   - Controllable compression
   - Multi-format summaries

4. **Context Templates**
   - Pre-configured contexts for common tasks
   - User-defined templates
   - Template marketplace

5. **Real-Time Adaptation**
   - Adjust context based on conversation
   - Dynamic reloading
   - Streaming context updates

---

**Last Updated:** December 19, 2025
**Status:** Ready for implementation
**Dependencies:** Phase 1 ✅, Phase 2 ✅, Phase 3 ✅ Complete
