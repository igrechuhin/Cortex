"""Docstrings for refactoring operations tools.

Extracted to keep refactoring operations.py under 400 lines.
"""

SUGGEST_REFACTORING_DOCSTRING = """Generate intelligent refactoring suggestions to improve Memory Bank
structure and efficiency.

USE WHEN: User wants refactoring suggestions, user needs consolidation
ideas, user requests reorganization suggestions, user wants to improve
structure.

EXAMPLES: 'suggest refactoring for consolidation', 'find files to split',
'suggest reorganization', 'get refactoring opportunities'.

RETURNS: JSON with refactoring suggestions, similarity scores, and
recommendations.

This consolidated tool provides three types of refactoring suggestions to
help optimize your Memory Bank:

1. **consolidation**: Identifies opportunities to consolidate duplicate or
   highly similar content across multiple files. Uses similarity analysis
   to find files sharing common content that could be extracted into
   shared files and referenced via transclusion.

2. **splits**: Identifies oversized files that should be split into
   smaller, more focused files. Analyzes file size in tokens and suggests
   logical split points based on content structure (headings, sections,
   topics).

3. **reorganization**: Generates comprehensive reorganization plans to
   improve overall structure. Can optimize for reducing dependency depth,
   grouping by category/functionality, or reducing complexity.

Args:
    type: Type of refactoring suggestions to generate.
        - "consolidation": Find duplicate content to consolidate
        - "splits": Find large files to split
        - "reorganization": Generate structure reorganization plan

    min_similarity: Minimum similarity threshold for consolidation
        suggestions (0.0-1.0).
        Example: 0.75 (75% similarity required)
        Default: 0.80 (80% similarity)
        Higher values = stricter matching, fewer suggestions.
        Lower values = more lenient matching, more suggestions.
        Only applies to type="consolidation".

    size_threshold: Maximum file size in bytes before suggesting split.
        Example: 8000 (suggest split for files over 8KB)
        Default: 10000 (10KB, approximately 2500 tokens)
        Only applies to type="splits".

    goal: Optimization goal for reorganization.
        - "dependency_depth": Minimize dependency chain depth (default)
        - "category": Group files by functionality/category
        - "complexity": Reduce overall structural complexity
        Only applies to type="reorganization".

    preview_suggestion_id: ID of a specific suggestion to preview.
        Example: "consolidation_001"
        If provided, returns detailed preview instead of generating suggestions.
        Currently requires suggestion caching (future feature).

    show_diff: Whether to include file diff in preview.
        Default: True
        Only applies when preview_suggestion_id is provided.

    estimate_impact: Whether to estimate impact metrics in preview.
        Default: True
        Only applies when preview_suggestion_id is provided.

Returns:
    JSON string. For type="consolidation": status, type, min_similarity,
    opportunities (id, files, similarity, recommendation, confidence).
    For type="splits": status, type, size_threshold, recommendations.
    For type="reorganization": status, type, goal, plan (current_state,
    proposed_state, moves, new_structure). On error: status "error",
    error message, error_type.

Note:
    - Consolidation analysis uses content similarity algorithms and may
      take several seconds for large Memory Banks. Results are cached per
      session.
    - Split recommendations consider both file size and logical content
      boundaries (sections, headings). Files just under the threshold may
      not get suggestions.
    - Reorganization plans preserve all file content and dependencies.
      The tool only suggests moves, it does not execute them automatically.
    - The min_similarity threshold significantly affects results:
      0.80-0.90 is typical, 0.70-0.79 is lenient (more suggestions),
      0.91-1.0 is strict (fewer suggestions).
    - Size threshold is in bytes. Typical values: 8000-12000 bytes.
      Remember that 1 token ≈ 4 characters, so 10000 bytes ≈ 2500 tokens.
    - Preview functionality (preview_suggestion_id) requires suggestion
      caching which is planned for a future release. Currently returns
      informational message.
    - All suggestions include confidence scores (high/medium/low) based on analysis
      quality and the certainty of the recommendation.
    - Refactoring suggestions do not modify files. Use execute_refactoring tool
      to apply changes after reviewing suggestions.
"""
