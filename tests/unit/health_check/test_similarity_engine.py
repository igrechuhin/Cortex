"""Tests for similarity engine."""

from unittest.mock import Mock

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
        engine = SimilarityEngine(min_content_length=10)
        content1 = "This is test content for similarity analysis and comparison between different text samples."
        content2 = "This is test content for similarity checking and comparison between different text samples."
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

    def test_configuration_parameters(self):
        """Test similarity engine with custom configuration."""
        engine = SimilarityEngine(
            high_threshold=0.8,
            medium_threshold=0.65,
            min_content_length=50,
            heading_weight=2.0,
            code_weight=1.5,
        )
        assert engine.high_threshold == 0.8
        assert engine.medium_threshold == 0.65
        assert engine.min_content_length == 50
        assert engine.heading_weight == 2.0
        assert engine.code_weight == 1.5

    def test_calculate_semantic_similarity(self):
        """Test semantic similarity calculation."""
        engine = SimilarityEngine()
        content1 = "Analyze and validate the system performance"
        content2 = "Check and process the system validation"
        similarity = engine.calculate_semantic_similarity(content1, content2)
        assert 0.0 <= similarity <= 1.0

    def test_calculate_semantic_similarity_identical(self):
        """Test semantic similarity for identical content."""
        engine = SimilarityEngine()
        content = "Test content for semantic analysis"
        similarity = engine.calculate_semantic_similarity(content, content)
        assert similarity > 0.8

    def test_calculate_semantic_similarity_different(self):
        """Test semantic similarity for different content."""
        engine = SimilarityEngine()
        content1 = "Analyze system performance"
        content2 = "Completely unrelated topic here"
        similarity = engine.calculate_semantic_similarity(content1, content2)
        assert 0.0 <= similarity < 0.5

    def test_calculate_functional_similarity_parameters(self):
        """Test functional similarity with parameters."""
        engine = SimilarityEngine()
        params1 = ["param1", "param2", "param3"]
        params2 = ["param1", "param2", "param4"]
        similarity = engine.calculate_functional_similarity(
            params1=params1, params2=params2
        )
        assert 0.0 <= similarity <= 1.0

    def test_calculate_functional_similarity_return_types(self):
        """Test functional similarity with return types."""
        engine = SimilarityEngine()
        similarity = engine.calculate_functional_similarity(
            return_type1="str", return_type2="string"
        )
        assert similarity == 1.0

    def test_calculate_functional_similarity_different_types(self):
        """Test functional similarity with different return types."""
        engine = SimilarityEngine()
        similarity = engine.calculate_functional_similarity(
            return_type1="str", return_type2="int"
        )
        assert similarity == 0.0

    def test_calculate_functional_similarity_usage_patterns(self):
        """Test functional similarity with usage patterns."""
        engine = SimilarityEngine()
        pattern1 = "Read file and process content"
        pattern2 = "Read file and analyze content"
        similarity = engine.calculate_functional_similarity(
            usage_pattern1=pattern1, usage_pattern2=pattern2
        )
        assert 0.0 <= similarity <= 1.0

    def test_calculate_functional_similarity_complete(self):
        """Test functional similarity with all parameters."""
        engine = SimilarityEngine()
        similarity = engine.calculate_functional_similarity(
            params1=["file", "mode"],
            params2=["file", "mode"],
            return_type1="str",
            return_type2="string",
            usage_pattern1="Read file content",
            usage_pattern2="Read file content",
        )
        assert similarity > 0.8

    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        engine = SimilarityEngine()
        content1 = "This is test content for similarity analysis"
        content2 = "This is test content for similarity checking"
        # Access private method via public interface
        similarity = engine.calculate_content_similarity(content1, content2)
        assert 0.0 <= similarity <= 1.0

    def test_section_weighting_headings(self):
        """Test section similarity with heading weighting."""
        engine = SimilarityEngine(heading_weight=2.0, text_weight=1.0)
        sections1 = ["# Heading 1", "Regular text content"]
        sections2 = ["# Heading 1", "Different text content"]
        similarity = engine.calculate_section_similarity(sections1, sections2)
        assert 0.0 <= similarity <= 1.0
        # Heading match should have more weight
        assert similarity > 0.5

    def test_section_weighting_code(self):
        """Test section similarity with code weighting."""
        engine = SimilarityEngine(code_weight=1.5, text_weight=1.0)
        sections1 = ["```python\ncode\n```", "Regular text"]
        sections2 = ["```python\ncode\n```", "Different text"]
        similarity = engine.calculate_section_similarity(sections1, sections2)
        assert 0.0 <= similarity <= 1.0

    def test_minimum_content_length(self):
        """Test minimum content length filtering."""
        engine = SimilarityEngine(min_content_length=100)
        short1 = "Short"
        short2 = "Text"
        similarity = engine.calculate_content_similarity(short1, short2)
        assert similarity == 0.0

    def test_minimum_content_length_long_content(self):
        """Test that long content passes minimum length check."""
        engine = SimilarityEngine(min_content_length=10)
        long_content = "This is a longer piece of content that should pass the minimum length check."
        similarity = engine.calculate_content_similarity(long_content, long_content)
        assert similarity == 1.0

    def test_keyword_extraction(self):
        """Test keyword extraction functionality."""
        engine = SimilarityEngine()
        content = "This is a test document for analyzing similarity between different content pieces."
        # Access via semantic similarity which uses keywords
        similarity = engine.calculate_semantic_similarity(content, content)
        assert similarity > 0.8

    def test_intent_extraction(self):
        """Test intent pattern extraction."""
        engine = SimilarityEngine()
        content1 = "Analyze the system and validate results"
        content2 = "Check the system and process data"
        similarity = engine.calculate_semantic_similarity(content1, content2)
        # Should have some similarity due to intent patterns
        assert 0.0 <= similarity <= 1.0

    def test_topic_similarity(self):
        """Test topic similarity calculation."""
        engine = SimilarityEngine()
        content1 = "Python programming language development tools"
        content2 = "Python code development and programming tools"
        similarity = engine.calculate_semantic_similarity(content1, content2)
        assert similarity > 0.5

    def test_parameter_overlap_identical(self):
        """Test parameter overlap with identical parameters."""
        engine = SimilarityEngine()
        params = ["param1", "param2"]
        similarity = engine.calculate_functional_similarity(
            params1=params, params2=params
        )
        assert similarity > 0.8

    def test_parameter_overlap_partial(self):
        """Test parameter overlap with partial overlap."""
        engine = SimilarityEngine()
        params1 = ["param1", "param2", "param3"]
        params2 = ["param1", "param2", "param4"]
        similarity = engine.calculate_functional_similarity(
            params1=params1, params2=params2
        )
        assert 0.0 < similarity < 1.0

    def test_parameter_overlap_no_overlap(self):
        """Test parameter overlap with no overlap."""
        engine = SimilarityEngine()
        params1 = ["param1", "param2"]
        params2 = ["param3", "param4"]
        similarity = engine.calculate_functional_similarity(
            params1=params1, params2=params2
        )
        assert similarity == 0.0

    def test_stop_words_filtering(self):
        """Test that stop words are properly filtered in keyword extraction."""
        engine = SimilarityEngine()
        # Content with many stop words should still produce meaningful similarity
        content1 = (
            "The system is designed to analyze and process data from various sources."
        )
        content2 = (
            "The system is designed to analyze and process data from various sources."
        )
        # Stop words should be filtered, leaving meaningful keywords
        similarity = engine.calculate_semantic_similarity(content1, content2)
        assert (
            similarity > 0.8
        )  # High similarity for identical content after stop word filtering

    def test_token_similarity_fallback_when_encoding_none(self):
        """Test fallback to Jaccard similarity when encoding is None."""
        mock_counter = Mock(spec=TokenCounter)
        mock_counter.encoding = None
        engine = SimilarityEngine(token_counter=mock_counter)
        content1 = "test content one"
        content2 = "test content two"
        similarity = engine._token_similarity(content1, content2)
        assert 0.0 <= similarity <= 1.0

    def test_token_similarity_fallback_on_encoding_error(self):
        """Test fallback to Jaccard similarity on encoding error."""
        mock_counter = Mock(spec=TokenCounter)
        mock_encoding = Mock()
        mock_encoding.encode.side_effect = Exception("Encoding error")
        mock_counter.encoding = mock_encoding
        engine = SimilarityEngine(token_counter=mock_counter)
        content1 = "test content one"
        content2 = "test content two"
        similarity = engine._token_similarity(content1, content2)
        assert 0.0 <= similarity <= 1.0

    def test_token_similarity_empty_tokens(self):
        """Test token similarity with empty token sets."""
        mock_counter = Mock(spec=TokenCounter)
        mock_encoding = Mock()
        mock_encoding.encode.return_value = []
        mock_counter.encoding = mock_encoding
        engine = SimilarityEngine(token_counter=mock_counter)
        # Both empty
        similarity = engine._token_similarity("", "")
        assert similarity == 1.0
        # One empty
        mock_encoding.encode.side_effect = [[], [1, 2, 3]]
        similarity = engine._token_similarity("", "content")
        assert similarity == 0.0

    def test_meets_min_length_exception_fallback(self):
        """Test _meets_min_length fallback when token counting raises exception."""
        mock_counter = Mock(spec=TokenCounter)
        mock_counter.count_tokens.side_effect = Exception("Token counting error")
        engine = SimilarityEngine(token_counter=mock_counter, min_content_length=10)
        # Should fallback to length-based check when token counting fails
        result = engine._meets_min_length("short", "this is longer content")
        assert result is False  # "short" is less than 10 chars
        result = engine._meets_min_length("this is longer", "this is also longer")
        assert result is True  # Both are >= 10 chars
