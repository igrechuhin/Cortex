"""Tests for similarity engine."""

from cortex.core.token_counter import TokenCounter
from cortex.health_check.similarity_engine import SimilarityEngine


class TestSimilarityEngine:
    """Test similarity engine functionality."""

    def test_calculate_content_similarity_identical(self):
        """Test similarity calculation for identical content."""
        engine = SimilarityEngine()
        content = "This is test content."
        similarity = engine.calculate_content_similarity(content, content)
        assert similarity == 1.0

    def test_calculate_content_similarity_different(self):
        """Test similarity calculation for different content."""
        engine = SimilarityEngine()
        content1 = "This is test content."
        content2 = "Completely different text here."
        similarity = engine.calculate_content_similarity(content1, content2)
        assert 0.0 <= similarity < 0.7  # Allow higher similarity due to word overlap

    def test_calculate_content_similarity_similar(self):
        """Test similarity calculation for similar content."""
        engine = SimilarityEngine()
        content1 = "This is test content for similarity."
        content2 = "This is test content for similarity check."
        similarity = engine.calculate_content_similarity(content1, content2)
        assert similarity > 0.7

    def test_calculate_content_similarity_empty(self):
        """Test similarity calculation with empty content."""
        engine = SimilarityEngine()
        similarity = engine.calculate_content_similarity("", "")
        assert similarity == 0.0

    def test_calculate_section_similarity(self):
        """Test section similarity calculation."""
        engine = SimilarityEngine()
        sections1 = ["Section 1", "Section 2"]
        sections2 = ["Section 1", "Section 3"]
        similarity = engine.calculate_section_similarity(sections1, sections2)
        assert 0.0 <= similarity <= 1.0

    def test_calculate_section_similarity_empty(self):
        """Test section similarity with empty sections."""
        engine = SimilarityEngine()
        similarity = engine.calculate_section_similarity([], [])
        assert similarity == 0.0

    def test_with_custom_token_counter(self):
        """Test similarity engine with custom token counter."""
        token_counter = TokenCounter()
        engine = SimilarityEngine(token_counter=token_counter)
        content = "Test content"
        similarity = engine.calculate_content_similarity(content, content)
        assert similarity == 1.0
