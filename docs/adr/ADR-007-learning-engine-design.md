# ADR-007: Learning Engine Design

## Status

Accepted

## Context

Cortex provides automated refactoring suggestions to improve memory bank quality. However, automated suggestions are never 100% accurate. We need a way to:

1. **Learn from user feedback**: When users accept or reject suggestions
2. **Improve over time**: Suggestions get better with usage
3. **Personalize**: Adapt to user preferences and project patterns
4. **Share knowledge**: Learn across projects and users
5. **Explain decisions**: Why a suggestion was made

### The Learning Problem

**Static Rules** (no learning):
```python
def suggest_consolidation(files: list[File]) -> list[Suggestion]:
    """Suggest consolidation based on fixed rules."""
    suggestions = []
    for f1, f2 in combinations(files, 2):
        if similarity(f1, f2) > 0.8:  # Fixed threshold
            suggestions.append(Consolidate(f1, f2))
    return suggestions
```

**Problems**:
- Fixed threshold doesn't work for all projects
- Can't learn user preferences (some want 0.7, others 0.9)
- No improvement over time
- Same mistakes repeated
- No adaptation to project patterns

### Requirements

**Functional Requirements**:
- Capture user feedback (accept/reject/modify)
- Learn from feedback to improve future suggestions
- Personalize to user/project preferences
- Explain why suggestions were made
- Support multiple learning signals (explicit and implicit)

**Non-Functional Requirements**:
- Privacy-preserving (no sensitive data sent to cloud)
- Fast learning (updates in real-time)
- Explainable (show why confidence changed)
- Robust (handle contradictory feedback)
- Storage-efficient (learning data should be small)

**Design Constraints**:
- Local-first (no required cloud dependency)
- No machine learning libraries (keep dependencies minimal)
- Simple algorithms (interpretable, debuggable)
- Fast inference (<10ms for confidence calculation)

### Learning Signals

**Explicit Feedback**:
1. **Accept**: User approves and applies suggestion
2. **Reject**: User explicitly dismisses suggestion
3. **Modify**: User edits suggestion before applying
4. **Revert**: User undoes applied suggestion

**Implicit Feedback**:
1. **Ignored**: Suggestion shown but not acted on
2. **Manual Action**: User performs suggested action without using tool
3. **Repeated Rejection**: Same suggestion type rejected multiple times
4. **Patterns**: User's actual refactoring patterns

**Context Features**:
1. **File similarity**: How similar are files being consolidated?
2. **File size**: How large are files involved?
3. **Duplication percentage**: How much content is duplicated?
4. **Dependency count**: How many dependencies involved?
5. **Project age**: How mature is the project?

### Use Cases

**Use Case 1: Threshold Learning**

User consistently rejects consolidation suggestions with similarity < 0.85:

```
Suggestion 1: Consolidate A + B (similarity=0.75) → Rejected
Suggestion 2: Consolidate C + D (similarity=0.78) → Rejected
Suggestion 3: Consolidate E + F (similarity=0.82) → Rejected
Suggestion 4: Consolidate G + H (similarity=0.88) → Accepted

Learning: User's threshold is ~0.85, not 0.75
```

**Use Case 2: Pattern Preferences**

User prefers splitting by domain, not by size:

```
Suggestion 1: Split file by size (200 lines) → Rejected
Suggestion 2: Split file by domain (API vs UI) → Accepted
Suggestion 3: Split file by size (250 lines) → Rejected
Suggestion 4: Split file by domain (Data vs Logic) → Accepted

Learning: User prefers domain-based splitting
```

**Use Case 3: Project-Specific Patterns**

Different projects have different conventions:

```
Project A: Accept consolidation at 0.7 similarity
Project B: Accept consolidation at 0.9 similarity

Learning: Store per-project preferences
```

**Use Case 4: Confidence Scoring**

Show confidence in suggestions based on historical data:

```
Suggestion: Consolidate X + Y (similarity=0.82)
  Historical similar suggestions: 5 accepted, 2 rejected
  Confidence: 71% (5/7)
```

### Design Space

**Machine Learning Approaches**:

1. **Supervised Learning**: Train on labeled data
   - Pros: Accurate, handles complex patterns
   - Cons: Requires ML library, slow, not interpretable

2. **Reinforcement Learning**: Learn from rewards
   - Pros: Adapts over time
   - Cons: Complex, requires lots of data

3. **Rule Learning**: Learn decision rules
   - Pros: Interpretable, simple
   - Cons: Limited expressiveness

4. **Bayesian Learning**: Update probabilities
   - Pros: Handles uncertainty well
   - Cons: Complex math

5. **Simple Statistics**: Count accept/reject rates
   - Pros: Simple, fast, interpretable
   - Cons: Limited learning capability

**Storage Approaches**:

1. **Feature Weights**: Store weights for each feature
2. **Decision Trees**: Store learned decision tree
3. **Lookup Tables**: Store acceptance rates per pattern
4. **Rule Database**: Store if-then rules
5. **Historical Log**: Store all feedback events

## Decision

We will implement a **lightweight statistical learning engine** based on:

1. **Feature-based feedback storage**: Store feedback with associated features
2. **Confidence scoring**: Calculate confidence from historical accept/reject rates
3. **Threshold learning**: Adjust thresholds based on feedback patterns
4. **Local storage**: All learning data stored locally (`.memory-bank-learning.json`)
5. **Explainable**: Clear explanation of why confidence is what it is

### Architecture

**LearningEngine** (`src/cortex/learning/learning_engine.py`):

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class FeedbackEvent:
    """User feedback on a suggestion."""
    suggestion_id: str
    suggestion_type: str  # "consolidation", "split", etc.
    action: str  # "accept", "reject", "modify", "revert"
    features: dict[str, float]  # Feature values
    timestamp: datetime
    project_id: str | None = None

@dataclass
class ConfidenceScore:
    """Confidence in a suggestion."""
    confidence: float  # 0.0 to 1.0
    reason: str  # Explanation
    historical_accepts: int
    historical_rejects: int
    similar_feedback_count: int

class LearningEngine:
    """Learn from user feedback."""

    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.feedback_history: list[FeedbackEvent] = []

    async def record_feedback(
        self,
        suggestion_id: str,
        suggestion_type: str,
        action: str,
        features: dict[str, float],
        project_id: str | None = None
    ) -> None:
        """Record user feedback."""
        event = FeedbackEvent(
            suggestion_id=suggestion_id,
            suggestion_type=suggestion_type,
            action=action,
            features=features,
            timestamp=datetime.now(),
            project_id=project_id
        )
        self.feedback_history.append(event)
        await self._persist()

    async def calculate_confidence(
        self,
        suggestion_type: str,
        features: dict[str, float],
        project_id: str | None = None
    ) -> ConfidenceScore:
        """Calculate confidence in suggestion."""
        # Find similar historical suggestions
        similar = self._find_similar_feedback(
            suggestion_type,
            features,
            project_id
        )

        if not similar:
            # No history - moderate confidence
            return ConfidenceScore(
                confidence=0.5,
                reason="No historical data for this suggestion type",
                historical_accepts=0,
                historical_rejects=0,
                similar_feedback_count=0
            )

        # Count accepts vs rejects
        accepts = sum(1 for e in similar if e.action == "accept")
        rejects = sum(1 for e in similar if e.action == "reject")
        total = accepts + rejects

        # Calculate confidence (with smoothing)
        confidence = (accepts + 1) / (total + 2)

        return ConfidenceScore(
            confidence=confidence,
            reason=f"Based on {total} similar suggestions",
            historical_accepts=accepts,
            historical_rejects=rejects,
            similar_feedback_count=len(similar)
        )

    def _find_similar_feedback(
        self,
        suggestion_type: str,
        features: dict[str, float],
        project_id: str | None,
        similarity_threshold: float = 0.8
    ) -> list[FeedbackEvent]:
        """Find similar historical feedback."""
        similar = []

        for event in self.feedback_history:
            # Must be same suggestion type
            if event.suggestion_type != suggestion_type:
                continue

            # Prefer same project
            if project_id and event.project_id != project_id:
                continue

            # Calculate feature similarity
            sim = self._calculate_similarity(features, event.features)
            if sim >= similarity_threshold:
                similar.append(event)

        return similar

    def _calculate_similarity(
        self,
        features1: dict[str, float],
        features2: dict[str, float]
    ) -> float:
        """Calculate feature similarity (cosine similarity)."""
        # Get common feature keys
        keys = set(features1.keys()) & set(features2.keys())
        if not keys:
            return 0.0

        # Calculate dot product and magnitudes
        dot_product = sum(features1[k] * features2[k] for k in keys)
        mag1 = sum(features1[k] ** 2 for k in keys) ** 0.5
        mag2 = sum(features2[k] ** 2 for k in keys) ** 0.5

        if mag1 == 0 or mag2 == 0:
            return 0.0

        return dot_product / (mag1 * mag2)
```

### Feature Engineering

**Consolidation Features**:
```python
def extract_consolidation_features(
    file1: str,
    file2: str
) -> dict[str, float]:
    """Extract features for consolidation suggestion."""
    return {
        "similarity": calculate_similarity(file1, file2),
        "size_ratio": min_size / max_size,
        "total_size": size1 + size2,
        "dependency_overlap": len(shared_deps) / len(total_deps),
        "same_directory": 1.0 if same_dir else 0.0,
        "duplication_percentage": dup_lines / total_lines,
    }
```

**Split Features**:
```python
def extract_split_features(file: str) -> dict[str, float]:
    """Extract features for split suggestion."""
    return {
        "file_size": line_count,
        "complexity": calculate_complexity(file),
        "section_count": count_sections(file),
        "average_section_size": total_lines / section_count,
        "has_clear_boundaries": 1.0 if has_boundaries else 0.0,
    }
```

### Threshold Learning

**Adaptive Thresholds**:

```python
class LearningEngine:
    async def learn_threshold(
        self,
        feature_name: str,
        suggestion_type: str
    ) -> float:
        """Learn optimal threshold for a feature."""
        # Get all feedback for this suggestion type
        feedback = [
            e for e in self.feedback_history
            if e.suggestion_type == suggestion_type
        ]

        if not feedback:
            # No data - use default
            return DEFAULT_THRESHOLDS[suggestion_type][feature_name]

        # Sort by feature value
        feedback.sort(key=lambda e: e.features.get(feature_name, 0))

        # Find threshold that maximizes accuracy
        best_threshold = 0.0
        best_accuracy = 0.0

        for i, event in enumerate(feedback):
            threshold = event.features.get(feature_name, 0)

            # Calculate accuracy with this threshold
            correct = 0
            total = 0

            for other in feedback:
                value = other.features.get(feature_name, 0)
                predicted_accept = value >= threshold
                actual_accept = other.action == "accept"

                if predicted_accept == actual_accept:
                    correct += 1
                total += 1

            accuracy = correct / total if total > 0 else 0

            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_threshold = threshold

        return best_threshold
```

### Storage Format

**Learning Data** (`.memory-bank-learning.json`):

```json
{
  "version": "1.0",
  "feedback_history": [
    {
      "suggestion_id": "consolidate-001",
      "suggestion_type": "consolidation",
      "action": "accept",
      "features": {
        "similarity": 0.85,
        "size_ratio": 0.9,
        "total_size": 450,
        "dependency_overlap": 0.7,
        "same_directory": 1.0,
        "duplication_percentage": 0.3
      },
      "timestamp": "2024-01-10T12:00:00Z",
      "project_id": "cortex"
    },
    {
      "suggestion_id": "split-001",
      "suggestion_type": "split",
      "action": "reject",
      "features": {
        "file_size": 250,
        "complexity": 15,
        "section_count": 3,
        "average_section_size": 83,
        "has_clear_boundaries": 0.0
      },
      "timestamp": "2024-01-10T12:05:00Z",
      "project_id": "cortex"
    }
  ],
  "learned_thresholds": {
    "consolidation": {
      "similarity": 0.82,
      "size_ratio": 0.75,
      "duplication_percentage": 0.25
    },
    "split": {
      "file_size": 300,
      "complexity": 20,
      "section_count": 4
    }
  },
  "statistics": {
    "total_feedback_events": 42,
    "accept_rate": 0.67,
    "reject_rate": 0.24,
    "modify_rate": 0.09
  }
}
```

### Integration with Refactoring

**Refactoring Suggestion with Confidence**:

```python
@dataclass
class RefactoringSuggestion:
    """Refactoring suggestion with confidence."""
    id: str
    type: str
    description: str
    files: list[str]
    confidence: ConfidenceScore
    features: dict[str, float]

async def get_refactoring_suggestions() -> list[RefactoringSuggestion]:
    """Get suggestions with confidence scores."""
    # Generate candidate suggestions
    candidates = await engine.generate_suggestions()

    # Calculate confidence for each
    suggestions = []
    for candidate in candidates:
        confidence = await learning_engine.calculate_confidence(
            suggestion_type=candidate.type,
            features=candidate.features,
            project_id=get_project_id()
        )

        suggestions.append(RefactoringSuggestion(
            id=candidate.id,
            type=candidate.type,
            description=candidate.description,
            files=candidate.files,
            confidence=confidence,
            features=candidate.features
        ))

    # Sort by confidence (highest first)
    suggestions.sort(key=lambda s: s.confidence.confidence, reverse=True)

    return suggestions
```

**Feedback Recording**:

```python
@mcp.tool()
async def approve_refactoring(
    suggestion_id: str,
    action: str  # "accept", "reject", "modify"
) -> dict[str, object]:
    """Record feedback on refactoring suggestion."""
    # Get suggestion details
    suggestion = await get_suggestion(suggestion_id)

    # Record feedback
    await learning_engine.record_feedback(
        suggestion_id=suggestion_id,
        suggestion_type=suggestion.type,
        action=action,
        features=suggestion.features,
        project_id=get_project_id()
    )

    return {
        "recorded": True,
        "message": f"Feedback recorded: {action}"
    }
```

## Consequences

### Positive

**1. Continuous Improvement**:
- Suggestions get better over time
- Learns from mistakes
- Adapts to user preferences
- No manual threshold tuning

**2. Personalization**:
- Per-project preferences
- Per-user preferences (future)
- Adapts to project patterns
- Respects user decisions

**3. Explainability**:
- Clear confidence scores
- Explanation of why confidence is what it is
- Historical data visible
- Debuggable

**4. Privacy-Preserving**:
- All data stored locally
- No cloud dependency
- User controls data
- No sensitive data exposure

**5. Lightweight**:
- No ML dependencies
- Simple statistics
- Fast (<10ms inference)
- Small storage footprint

**6. Robust**:
- Handles contradictory feedback
- Smoothing prevents overfitting
- Graceful handling of edge cases
- No catastrophic forgetting

### Negative

**1. Limited Learning Capability**:
- Simple statistics only
- Can't learn complex patterns
- No feature interaction modeling
- Linear relationships only

**2. Cold Start Problem**:
- No history initially
- Moderate confidence for new types
- Requires feedback to improve
- Slow learning at first

**3. Storage Growth**:
- Feedback history grows over time
- No automatic pruning
- May need manual cleanup
- Could impact performance with 1000s of events

**4. Feature Engineering**:
- Manual feature selection required
- Features may not capture all factors
- Requires domain expertise
- Hard to know which features matter

**5. No Cross-Project Learning**:
- Each project starts from scratch
- Can't leverage common patterns
- Duplicated learning across projects
- Could benefit from aggregation

**6. Implicit Feedback Limited**:
- Only explicit feedback used initially
- Ignoring rich implicit signals
- Could learn more from behavior
- Requires additional implementation

### Neutral

**1. Feature Similarity**:
- Cosine similarity chosen (other metrics possible)
- Works well for normalized features
- May not be optimal for all cases
- Could experiment with alternatives

**2. Smoothing**:
- Laplace smoothing used (add-one)
- Prevents zero confidence
- Conservative approach
- Could use other smoothing techniques

**3. Threshold Learning**:
- Accuracy maximization chosen
- Could optimize other metrics (F1, precision, recall)
- Context-dependent choice
- May need tuning

## Alternatives Considered

### Alternative 1: No Learning (Static Rules)

**Approach**: Fixed thresholds and rules.

**Pros**:
- Simple
- Predictable
- No storage needed
- Fast

**Cons**:
- No improvement
- Can't adapt
- Same mistakes repeated
- Manual tuning needed

**Rejection Reason**: Doesn't meet requirement for continuous improvement.

### Alternative 2: Machine Learning (scikit-learn)

**Approach**: Use supervised learning with scikit-learn.

```python
from sklearn.ensemble import RandomForestClassifier

class MLLearningEngine:
    def __init__(self):
        self.model = RandomForestClassifier()

    async def train(self, feedback: list[FeedbackEvent]):
        X = [list(e.features.values()) for e in feedback]
        y = [1 if e.action == "accept" else 0 for e in feedback]
        self.model.fit(X, y)

    async def predict_confidence(self, features: dict[str, float]) -> float:
        X = [list(features.values())]
        return self.model.predict_proba(X)[0][1]
```

**Pros**:
- More accurate
- Handles complex patterns
- Learns feature interactions
- Proven algorithms

**Cons**:
- Heavy dependency (scikit-learn)
- Slow training/inference
- Not interpretable
- Overkill for simple cases

**Rejection Reason**: Violates constraint of minimal dependencies. Too complex for needs.

### Alternative 3: Reinforcement Learning

**Approach**: Model as RL problem with rewards.

**Pros**:
- Optimal for sequential decisions
- Learns from delayed rewards
- Handles exploration/exploitation

**Cons**:
- Very complex
- Requires lots of data
- Hard to debug
- Overkill

**Rejection Reason**: Way too complex. Overkill for this use case.

### Alternative 4: Cloud-Based Learning

**Approach**: Send feedback to cloud, learn centrally.

**Pros**:
- Cross-project learning
- More data = better learning
- Shared knowledge
- Professional ML infrastructure

**Cons**:
- Privacy concerns
- Requires cloud dependency
- Network latency
- Vendor lock-in

**Rejection Reason**: Violates privacy-preserving requirement. Local-first is core principle.

### Alternative 5: Rule Mining

**Approach**: Mine association rules from feedback.

```python
# Example: If similarity > 0.8 AND same_directory THEN accept
```

**Pros**:
- Interpretable rules
- Easy to understand
- Explainable
- Fast inference

**Cons**:
- Hard to mine automatically
- Requires lots of data
- Rigid (hard thresholds)
- Can't handle uncertainty

**Rejection Reason**: Rule mining requires significant data. Hard to implement well.

### Alternative 6: Bayesian Network

**Approach**: Model dependencies between features as Bayesian network.

**Pros**:
- Handles uncertainty well
- Models feature dependencies
- Probabilistically sound
- Good with sparse data

**Cons**:
- Complex implementation
- Hard to visualize
- Slow inference
- Requires expert knowledge

**Rejection Reason**: Too complex to implement without libraries. Overkill.

### Alternative 7: Lookup Table

**Approach**: Store exact feature vectors and outcomes.

```python
lookup_table = {
    (0.85, 0.9, 450): "accept",
    (0.75, 0.8, 300): "reject",
}
```

**Pros**:
- Simple
- Fast lookup
- Exact matching
- Easy to implement

**Cons**:
- No generalization
- Exact matches rare
- Storage explodes
- Doesn't handle new situations

**Rejection Reason**: Can't generalize to new feature combinations. Not practical.

## Implementation Notes

### Data Privacy

All learning data stays local:
- Stored in `.memory-bank-learning.json`
- Never sent to cloud
- User controls data
- Can be deleted anytime

### Performance Optimization

**Indexing**:
```python
class LearningEngine:
    def __init__(self):
        # Index feedback by suggestion type
        self._index: dict[str, list[FeedbackEvent]] = {}

    def _find_similar_feedback(self, suggestion_type: str, ...):
        # Only search relevant subset
        candidates = self._index.get(suggestion_type, [])
```

**Caching**:
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def calculate_similarity(features1_tuple, features2_tuple):
    """Cached similarity calculation."""
    ...
```

### Future Enhancements

**Phase 1** (Current): Basic statistical learning
**Phase 2**: Implicit feedback (ignored suggestions)
**Phase 3**: Cross-project aggregation (opt-in, privacy-preserving)
**Phase 4**: Advanced ML (optional, with user consent)

### Testing Strategy

**Unit Tests**:
- Test confidence calculation
- Test similarity calculation
- Test threshold learning
- Test feedback storage

**Integration Tests**:
- Test full learning loop
- Test persistence
- Test with real feedback patterns

**Simulation Tests**:
- Simulate user feedback
- Verify learning convergence
- Test edge cases

## References

- [Online Learning](https://en.wikipedia.org/wiki/Online_machine_learning)
- [Collaborative Filtering](https://en.wikipedia.org/wiki/Collaborative_filtering)
- [Laplace Smoothing](https://en.wikipedia.org/wiki/Additive_smoothing)
- [Cosine Similarity](https://en.wikipedia.org/wiki/Cosine_similarity)
- [Explainable AI](https://en.wikipedia.org/wiki/Explainable_artificial_intelligence)

## Related ADRs

- ADR-001: Hybrid Storage - Where learning data is stored
- ADR-006: Async-First Design - Async learning operations
- ADR-008: Security Model - Privacy protection

## Revision History

- 2024-01-10: Initial version (accepted)
