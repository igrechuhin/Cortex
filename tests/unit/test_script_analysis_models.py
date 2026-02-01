"""Tests for script_analysis Pydantic models."""

from cortex.script_analysis.models import (
    GapAnalysis,
    ScriptAnalysisResult,
    SimilarityPair,
    UseCaseExtraction,
)


class TestUseCaseExtraction:
    """Tests for UseCaseExtraction model."""

    def test_creates_with_required_fields(self) -> None:
        """UseCaseExtraction requires use_case_label."""
        u = UseCaseExtraction(use_case_label="format code")
        assert u.use_case_label == "format code"
        assert u.keywords == []

    def test_creates_with_keywords(self) -> None:
        """UseCaseExtraction accepts keywords list."""
        u = UseCaseExtraction(
            use_case_label="run tests",
            keywords=["test", "pytest", "run"],
        )
        assert u.keywords == ["test", "pytest", "run"]


class TestGapAnalysis:
    """Tests for GapAnalysis model."""

    def test_creates_gap_true(self) -> None:
        """GapAnalysis with is_gap=True and gap_reason."""
        g = GapAnalysis(
            existing_tool_names=[],
            existing_script_names=[],
            gap_reason="No existing tool covers this",
            is_gap=True,
        )
        assert g.is_gap is True
        assert g.existing_tool_names == []
        assert g.gap_reason == "No existing tool covers this"

    def test_creates_gap_false_with_overlaps(self) -> None:
        """GapAnalysis with is_gap=False and overlapping names."""
        g = GapAnalysis(
            existing_tool_names=["check_formatting"],
            existing_script_names=["fix_formatting.py"],
            gap_reason="Overlapping tools: check_formatting",
            is_gap=False,
        )
        assert g.is_gap is False
        assert "check_formatting" in g.existing_tool_names
        assert "fix_formatting.py" in g.existing_script_names


class TestSimilarityPair:
    """Tests for SimilarityPair model."""

    def test_creates_with_ids_and_score(self) -> None:
        """SimilarityPair has script_id_1, script_id_2, similarity_score."""
        p = SimilarityPair(
            script_id_1="id-a",
            script_id_2="id-b",
            similarity_score=0.85,
        )
        assert p.script_id_1 == "id-a"
        assert p.script_id_2 == "id-b"
        assert p.similarity_score == 0.85

    def test_score_bounds_0_1(self) -> None:
        """Similarity_score must be between 0 and 1."""
        p0 = SimilarityPair(
            script_id_1="a",
            script_id_2="b",
            similarity_score=0.0,
        )
        p1 = SimilarityPair(
            script_id_1="a",
            script_id_2="b",
            similarity_score=1.0,
        )
        assert p0.similarity_score == 0.0
        assert p1.similarity_score == 1.0


class TestScriptAnalysisResult:
    """Tests for ScriptAnalysisResult model."""

    def test_creates_with_required_fields(self) -> None:
        """ScriptAnalysisResult requires script_id, use_case, gap."""
        use_case = UseCaseExtraction(use_case_label="lint")
        gap = GapAnalysis(
            existing_tool_names=[],
            existing_script_names=[],
            gap_reason="Gap",
            is_gap=True,
        )
        r = ScriptAnalysisResult(
            script_id="sid-1",
            use_case=use_case,
            gap=gap,
        )
        assert r.script_id == "sid-1"
        assert r.use_case.use_case_label == "lint"
        assert r.gap.is_gap is True
        assert r.reusability_score == 0.5
        assert r.promotion_potential == 0.5

    def test_creates_with_scores(self) -> None:
        """ScriptAnalysisResult accepts reusability_score and promotion_potential."""
        use_case = UseCaseExtraction(use_case_label="test")
        gap = GapAnalysis(
            existing_tool_names=[],
            existing_script_names=[],
            gap_reason="Gap",
            is_gap=True,
        )
        r = ScriptAnalysisResult(
            script_id="sid-2",
            use_case=use_case,
            gap=gap,
            reusability_score=0.8,
            promotion_potential=0.9,
        )
        assert r.reusability_score == 0.8
        assert r.promotion_potential == 0.9
