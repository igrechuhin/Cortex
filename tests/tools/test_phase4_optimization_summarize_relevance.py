# ruff: noqa: F403,F405
"""Split tests from Phase 4 optimization suite."""

from tests.tools.phase4_optimization_common import *  # noqa: F401,F403,F405

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.token_counter import TokenCounter
from cortex.optimization.config import OptimizationConfig
from cortex.optimization.models import SummarizationResultModel
from cortex.optimization.summarization_engine import SummarizationEngine
from cortex.tools.optimization.summarization_operations import summarize_content_impl


class _InvertingScorer:
    """Test double: inverts the heuristic's verdict for one document.

    Scores the section named ``favored_name`` at 1.0 and everything else at
    0.0, so a tight budget keeps that section instead of whatever
    ``HeuristicSectionScorer`` would have favored.
    """

    def __init__(self, favored_name: str) -> None:
        self.identity = f"inverting-{favored_name}"
        self._favored_name = favored_name

    def score(self, section_name: str, content: str) -> float:
        return 1.0 if section_name == self._favored_name else 0.0


def _build_managers(
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    optimization_config: OptimizationConfig,
    summarization_engine: SummarizationEngine,
) -> ManagersDict:
    """Assemble the ManagersDict shape summarize_content_impl expects."""
    return ManagersDict.model_construct(
        fs=fs_manager,
        index=metadata_index,
        optimization_config=optimization_config,
        summarization_engine=summarization_engine,
    )


def _graduated_sections_content() -> str:
    """Three sections of increasing size and decreasing score, so a lenient
    0.1 target only has to drop the huge "Example" section while a strict
    0.8 target must also drop the medium "Background" section too --
    different targets must select different sections, not just differ by
    a rounding hair.
    """
    return (
        "# Overview\n"
        + ("Overview content. " * 8)
        + "\n\n# Background\n"
        + ("Filler background text for context. " * 25)
        + "\n\n# Example\n"
        + ("Verbose example filler text that could be dropped. " * 26)
    )


@pytest.mark.timeout(15)
class TestSummarizeContent:
    """Tests for summarize_content() tool."""

    async def test_summarize_single_file(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarizing a single file."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.summarization_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await summarize_content(
                file_name="file1.md", target_reduction=0.5
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["files_summarized"] == 1
            assert result["target_reduction"] == 0.5

    async def test_summarize_all_files(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarizing all files."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.summarization_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await summarize_content()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["files_summarized"] == 2  # Mock returns 2 files

    async def test_summarize_uses_config_defaults_when_args_none(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarize_content uses config defaults when target_reduction and strategy are None."""
        mock_optimization_config = MagicMock()
        mock_optimization_config.is_summarization_enabled.return_value = True
        mock_optimization_config.get_summarization_target_reduction.return_value = 0.6
        mock_optimization_config.get_summarization_strategy.return_value = (
            "compress_verbose"
        )
        mock_optimization_config.is_optimization_enabled.return_value = True

        result = await run_summarize_with_config_overrides(
            mock_project_root,
            mock_managers,
            mock_optimization_config,
            _get_manager_helper,
        )
        # Defect 3 fix: the mocked engine always returns a 50% reduction;
        # against the configured 60% target that is a genuine miss, so the
        # call now correctly reports "error" instead of a blanket "success".
        assert result["status"] == "error"
        assert result["target_reduction"] == 0.6
        assert result["strategy"] == "compress_verbose"
        mock_optimization_config.get_summarization_target_reduction.assert_called_once()
        mock_optimization_config.get_summarization_strategy.assert_called_once()

    async def test_summarize_gated_on_summarization_enabled(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarize_content is gated on summarization.enabled."""
        # Arrange
        mock_optimization_config = MagicMock()
        mock_optimization_config.is_summarization_enabled.return_value = False
        mock_optimization_config.is_optimization_enabled.return_value = True

        def get_manager_helper(mgrs: ManagersDict, key: str, _: object) -> object:
            if key == "optimization_config":
                return mock_optimization_config
            return _get_manager_helper(mgrs, key, _)

        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.summarization_operations.get_manager",
                side_effect=get_manager_helper,
            ),
        ):
            # Act
            result_str = await summarize_content(file_name="file1.md")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "disabled" in result["error"].lower()

    async def test_optimization_tools_gated_on_top_level_enabled(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test optimization tools are gated on top-level enabled flag."""
        # Arrange
        mock_optimization_config = MagicMock()
        mock_optimization_config.is_optimization_enabled.return_value = False

        def get_manager_helper(mgrs: ManagersDict, key: str, _: object) -> object:
            if key == "optimization_config":
                return mock_optimization_config
            return _get_manager_helper(mgrs, key, _)

        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.handlers_load.get_manager",
                side_effect=get_manager_helper,
            ),
        ):
            # Act - test load_context (explicit budget so we reach disabled check)
            result_str = await _load_context_impl(
                task_description="test task", token_budget=50000
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "disabled" in result["error"].lower()

    async def test_summarize_with_strategy(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarization with different strategies."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.summarization_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await summarize_content(strategy="headers_only")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["strategy"] == "headers_only"

    async def test_summarize_invalid_reduction(self, mock_project_root: Path) -> None:
        """Test summarization with invalid reduction value."""
        # Arrange - no need to mock managers as validation happens first

        # Act
        result_str = await summarize_content(target_reduction=1.5)
        result = json.loads(result_str)

        # Assert
        assert result["status"] == "error"
        assert "target_reduction must be between 0 and 1" in result["error"]

    async def test_summarize_invalid_strategy(self, mock_project_root: Path) -> None:
        """Test summarization with invalid strategy."""
        # Arrange - no need to mock managers as validation happens first

        # Act
        result_str = await summarize_content(strategy="invalid_strategy")
        result = json.loads(result_str)

        # Assert
        assert result["status"] == "error"
        assert "Invalid strategy" in result["error"]

    async def test_summarize_exception_handling(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test exception handling in summarize_content."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.summarization_operations.get_manager",
                side_effect=RuntimeError("Summarization failed"),
            ),
        ):
            # Act
            result_str = await summarize_content()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"

    async def test_summarize_below_target_rejected_with_real_engine(
        self, mock_project_root: Path
    ) -> None:
        """Real SummarizationEngine over content that cannot hit target.

        Every other test in this module mocks summarization_engine.summarize_file,
        which is exactly why the below-target-still-ships-as-success defect
        survived undetected. This drives the genuine engine end to end over
        headers-only content (no body under any heading), so
        `passthrough_unsectioned` fires and there is nothing to reduce.
        """
        metadata_index = MetadataIndex(mock_project_root)
        fs_manager = FileSystemManager(mock_project_root)
        summarization_engine = SummarizationEngine(TokenCounter(), metadata_index)
        optimization_config = OptimizationConfig(mock_project_root)

        metadata_index.memory_bank_dir.mkdir(parents=True, exist_ok=True)
        unsectioned = "# Just A Heading\n# Another Heading\n# Third Heading"
        _ = (metadata_index.memory_bank_dir / "notes.md").write_text(unsectioned)

        managers = _build_managers(
            fs_manager, metadata_index, optimization_config, summarization_engine
        )

        result_str = await summarize_content_impl(
            managers, "notes.md", 0.5, "extract_key_sections"
        )
        result = json.loads(result_str)

        assert result["status"] == "error"
        assert "notes.md" in result["files_below_target"]
        rejected = result["results"][0]
        assert rejected["summary"] == ""
        assert rejected["rejected_reason"]

    async def test_summarize_plain_prose_passes_through_and_is_rejected(
        self, mock_project_root: Path
    ) -> None:
        """Headerless prose must pass through verbatim, not crash or shrink.

        Regression: `parse_sections` wraps headerless content in a synthetic
        "preamble" section, so reconstruction re-emitted the body under an
        invented "## preamble" heading. That made the summary LARGER than the
        input, driving `reduction` negative and raising ValidationError against
        SummarizationResultModel's ge=0.0 bound -- a 500 on ordinary prose.
        """
        metadata_index = MetadataIndex(mock_project_root)
        fs_manager = FileSystemManager(mock_project_root)
        summarization_engine = SummarizationEngine(TokenCounter(), metadata_index)
        optimization_config = OptimizationConfig(mock_project_root)

        metadata_index.memory_bank_dir.mkdir(parents=True, exist_ok=True)
        prose = "The build fails at src/app.py:42 with ImportError. " * 20
        _ = (metadata_index.memory_bank_dir / "prose.md").write_text(prose)

        managers = _build_managers(
            fs_manager, metadata_index, optimization_config, summarization_engine
        )

        result_str = await summarize_content_impl(
            managers, "prose.md", 0.5, "extract_key_sections"
        )
        result = json.loads(result_str)

        # Nothing to select between, so the target cannot be met: rejected.
        assert result["status"] == "error"
        assert "prose.md" in result["files_below_target"]
        rejected = result["results"][0]
        assert rejected["reduction"] == 0.0
        assert rejected["summary"] == ""
        assert rejected["rejected_reason"]
        # The file itself must be untouched -- pass-through, never a rewrite.
        assert (metadata_index.memory_bank_dir / "prose.md").read_text() == prose

    async def test_summarize_missing_file_reports_error_not_empty_success(
        self, mock_project_root: Path
    ) -> None:
        """A batch where every file was skipped must not report success.

        Recording the skip reason is only half the fix: if the response still
        says `success` with an empty result set, the caller learns nothing and
        the silent-skip defect simply moves one level up.
        """
        metadata_index = MetadataIndex(mock_project_root)
        metadata_index.memory_bank_dir.mkdir(parents=True, exist_ok=True)

        managers = _build_managers(
            FileSystemManager(mock_project_root),
            metadata_index,
            OptimizationConfig(mock_project_root),
            SummarizationEngine(TokenCounter(), metadata_index),
        )

        result = json.loads(
            await summarize_content_impl(
                managers, "nonexistent.md", 0.5, "extract_key_sections"
            )
        )

        assert result["status"] == "error"
        assert result["files_summarized"] == 0
        assert result["files_skipped"] == ["nonexistent.md"]
        assert "nonexistent.md" in result["error"]
        assert result["results"][0]["skipped_reason"]

    async def test_summarize_different_targets_not_served_stale_cache(
        self, mock_project_root: Path
    ) -> None:
        """Cache identity must include target_reduction, not just content+strategy.

        Regression: `target_tokens = int(original_tokens * (1 - target_reduction))`
        drives section selection, but the cache was keyed only on
        (file_name, strategy, content_hash). A summary generated for
        target_reduction=0.1 was served verbatim -- `cached=True` -- to a
        target_reduction=0.8 request on the same file, so `met_target` was
        computed against an artifact built for a different target.
        """
        metadata_index = MetadataIndex(mock_project_root)
        fs_manager = FileSystemManager(mock_project_root)
        summarization_engine = SummarizationEngine(TokenCounter(), metadata_index)
        optimization_config = OptimizationConfig(mock_project_root)

        metadata_index.memory_bank_dir.mkdir(parents=True, exist_ok=True)
        content = _graduated_sections_content()
        _ = (metadata_index.memory_bank_dir / "doc.md").write_text(content)

        managers = _build_managers(
            fs_manager, metadata_index, optimization_config, summarization_engine
        )

        low = json.loads(
            await summarize_content_impl(
                managers, "doc.md", 0.1, "extract_key_sections"
            )
        )
        high = json.loads(
            await summarize_content_impl(
                managers, "doc.md", 0.8, "extract_key_sections"
            )
        )
        low_result = low["results"][0]
        high_result = high["results"][0]

        # The regression: with a stale cache hit, high_result would come back
        # carrying low_result's summary/section-selection verbatim.
        assert high_result["summary"] != low_result["summary"]
        assert high_result["sections_kept"] < low_result["sections_kept"]
        assert high_result["reduction"] > low_result["reduction"]

    async def test_summarize_cache_hit_preserves_full_provenance(
        self, mock_project_root: Path
    ) -> None:
        """A cache hit must be indistinguishable from a fresh generation
        except for the `cached` flag: sections_kept/sections_removed/
        dropped_sections (including each drop's `reason`) round-trip
        through the cache rather than silently resetting to zero/empty.
        """
        metadata_index = MetadataIndex(mock_project_root)
        engine = SummarizationEngine(TokenCounter(), metadata_index)
        content = (
            "# Overview\n"
            + ("Overview content. " * 20)
            + "\n\n# Example\n"
            + ("Verbose example filler text that could be dropped. " * 120)
        )

        first = await engine.summarize_file(
            "doc.md", content, target_reduction=0.5, strategy="extract_key_sections"
        )
        second = await engine.summarize_file(
            "doc.md", content, target_reduction=0.5, strategy="extract_key_sections"
        )

        assert first["cached"] is False
        assert second["cached"] is True
        assert second["summary"] == first["summary"]
        assert second["sections_kept"] == first["sections_kept"]
        assert second["sections_removed"] == first["sections_removed"]
        assert second["dropped_sections"] == first["dropped_sections"]
        assert first["dropped_sections"]  # Example must have been dropped
        first_dropped = first["dropped_sections"]
        assert isinstance(first_dropped, list)
        first_dropped_entry = first_dropped[0]
        assert isinstance(first_dropped_entry, dict)
        assert first_dropped_entry["reason"] == "budget_exceeded"

    async def test_summarize_file_uses_injected_scorer_for_selection(
        self, mock_project_root: Path
    ) -> None:
        """The injected `SectionScorer`, not the heuristic, drives selection.

        `HeuristicSectionScorer` keyword-boosts "Overview" and penalizes
        "Example", so a tight budget keeps Overview and drops Example. A
        scorer that inverts that verdict must flip which section survives.
        """
        metadata_index = MetadataIndex(mock_project_root)
        content = (
            "# Overview\n"
            "Short overview text.\n\n"
            "# Notes\n"
            "Some notes text here.\n\n"
            "# Example\n"
            "Example section text that the heuristic would rank lowest.\n"
        )

        heuristic_engine = SummarizationEngine(TokenCounter(), metadata_index)
        fake_engine = SummarizationEngine(
            TokenCounter(), metadata_index, section_scorer=_InvertingScorer("Example")
        )

        heuristic_result = await heuristic_engine.summarize_file(
            "doc.md", content, target_reduction=0.7, strategy="extract_key_sections"
        )
        fake_result = await fake_engine.summarize_file(
            "doc.md", content, target_reduction=0.7, strategy="extract_key_sections"
        )

        heuristic_summary = heuristic_result["summary"]
        fake_summary = fake_result["summary"]
        assert isinstance(heuristic_summary, str)
        assert isinstance(fake_summary, str)

        assert "# Overview" in heuristic_summary
        assert "# Example" not in heuristic_summary
        assert "# Example" in fake_summary
        assert "# Overview" not in fake_summary
        assert fake_summary != heuristic_summary

    async def test_summarize_file_cache_key_isolated_by_scorer_identity(
        self, mock_project_root: Path
    ) -> None:
        """Two scorers over identical content/strategy/target must not share
        a cache entry, but a scorer must still reuse its own cache entry.
        """
        metadata_index = MetadataIndex(mock_project_root)
        content = (
            "# Overview\nShort overview text.\n\n"
            "# Notes\nSome notes text here.\n\n"
            "# Example\nExample section text that the heuristic would rank lowest.\n"
        )
        heuristic_engine = SummarizationEngine(TokenCounter(), metadata_index)
        fake_engine = SummarizationEngine(
            TokenCounter(), metadata_index, section_scorer=_InvertingScorer("Example")
        )

        heuristic_result = await heuristic_engine.summarize_file(
            "doc2.md", content, target_reduction=0.7, strategy="extract_key_sections"
        )
        fake_first = await fake_engine.summarize_file(
            "doc2.md", content, target_reduction=0.7, strategy="extract_key_sections"
        )
        fake_second = await fake_engine.summarize_file(
            "doc2.md", content, target_reduction=0.7, strategy="extract_key_sections"
        )

        # A different scorer identity must not be served the heuristic's hit.
        assert fake_first["cached"] is False
        assert fake_first["summary"] != heuristic_result["summary"]
        # The same scorer, called again, must still reuse its own hit.
        assert fake_second["cached"] is True
        assert fake_second["summary"] == fake_first["summary"]

    async def test_summarize_file_cache_key_discriminates_close_ratios(
        self, mock_project_root: Path
    ) -> None:
        """Two target_reduction values that round identically at 4 decimal
        places can still floor to different integer target_tokens budgets
        on real content. Keying the cache on the rounded ratio would let
        one silently serve the other's request; keying on target_tokens
        itself must not.
        """
        metadata_index = MetadataIndex(mock_project_root)
        token_counter = TokenCounter()
        engine = SummarizationEngine(token_counter, metadata_index)
        content = "Repeated filler sentence for scale purposes only. " * 3000

        target_reduction_a = 0.49999
        target_reduction_b = 0.50001
        # Both round to "0.5000" under the old (removed) 4dp-rounded scheme.
        assert f"{target_reduction_a:.4f}" == f"{target_reduction_b:.4f}"
        # ...yet floor to different integer token budgets on this content.
        original_tokens = token_counter.count_tokens(content)
        target_tokens_a = int(original_tokens * (1 - target_reduction_a))
        target_tokens_b = int(original_tokens * (1 - target_reduction_b))
        assert target_tokens_a != target_tokens_b

        result_a = await engine.summarize_file(
            "doc.md", content, target_reduction=target_reduction_a
        )
        result_b = await engine.summarize_file(
            "doc.md", content, target_reduction=target_reduction_b
        )

        assert result_a["cached"] is False
        # Not served from result_a's entry despite the rounding collision.
        assert result_b["cached"] is False

    async def test_extract_key_sections_never_grows_the_output(
        self, mock_project_root: Path
    ) -> None:
        """A tiny section with a very long heading used to cost more to
        disclose than to keep, so the "summary" grew. The omission note is now
        bounded by what it replaces, so this can no longer happen.
        """
        metadata_index = MetadataIndex(mock_project_root)
        engine = SummarizationEngine(TokenCounter(), metadata_index)
        long_name = (
            "VeryLongSectionNameForTestingGrowthCaseOverheadXYZ"
            "ExtraPaddingToMakeItEvenLonger"
        )
        content = f"# Overview\nKept.\n\n## {long_name}\nx\n"

        result = await engine.summarize_file(
            "doc.md", content, target_reduction=0.99, strategy="extract_key_sections"
        )

        summarized_tokens = result["summarized_tokens"]
        original_tokens = result["original_tokens"]
        reduction = result["reduction"]
        assert isinstance(summarized_tokens, int)
        assert isinstance(original_tokens, int)
        assert isinstance(reduction, float)
        assert summarized_tokens <= original_tokens
        assert reduction >= 0.0

    def test_result_model_still_represents_a_negative_reduction(self) -> None:
        """Growth is prevented in this strategy, not made unrepresentable:
        the field must still carry a true negative ratio rather than floor it,
        so any future lossy strategy reports growth instead of hiding it.
        """
        model = SummarizationResultModel(
            original_tokens=10,
            summary_tokens=14,
            reduction=-0.4,
            summary="grown",
            strategy="hypothetical",
        )

        assert model.reduction == -0.4
        assert model.met_target is False


# ============================================================================
# Test get_relevance_scores()
# ============================================================================


async def _index_file(
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
    token_counter: TokenCounter,
    file_name: str,
    content: str,
) -> None:
    """Write a memory-bank file and register it so list_all_files() sees it."""
    file_path = metadata_index.memory_bank_dir / file_name
    content_hash = await fs_manager.write_file(file_path, content)
    sections = fs_manager.parse_sections(content)
    await metadata_index.update_file_metadata(
        file_name=file_name,
        path=file_path,
        exists=True,
        size_bytes=len(content.encode("utf-8")),
        token_count=token_counter.count_tokens(content),
        content_hash=content_hash,
        sections=[section.model_dump(mode="json") for section in sections],
    )


@pytest.mark.parametrize(
    ("hits", "total", "expected_status"),
    [
        (1, 2, "error"),  # 50% — below the supermajority
        (2, 2, "success"),  # 100%
        (2, 4, "error"),  # 50%
        (3, 4, "success"),  # 75%
        (3, 10, "error"),  # 30% — a capped 3-of-5 rule would wrongly pass this
        (6, 10, "success"),  # 60% — exactly at the bar
    ],
)
async def test_batch_gate_scales_with_request_size(
    mock_project_root: Path, hits: int, total: int, expected_status: str
) -> None:
    """The hit-ratio gate must scale with the request, driven end to end
    through `summarize_content_impl` over real indexed memory-bank files --
    not just through the private ratio function in isolation.

    `hits` files carry a droppable low-value section (clearing a 0.5
    target); the rest are plain prose with nothing to select between
    (reduction stays 0.0, missing target). tools/compress/batch.py caps its
    thresholds at 3-of-5 because it samples a one-time sweep; reusing that
    rule here would wrongly pass 3-of-10.
    """
    metadata_index = MetadataIndex(mock_project_root)
    fs_manager = FileSystemManager(mock_project_root)
    token_counter = TokenCounter()
    summarization_engine = SummarizationEngine(token_counter, metadata_index)
    optimization_config = OptimizationConfig(mock_project_root)
    metadata_index.memory_bank_dir.mkdir(parents=True, exist_ok=True)

    droppable = "# Overview\nShort overview.\n\n# Example\n" + (
        "Verbose example filler text that should be dropped. " * 60
    )
    passthrough = (
        "Plain prose with nothing to select between, so nothing is ever dropped.\n"
    )
    for i in range(total):
        content = droppable if i < hits else passthrough
        await _index_file(
            metadata_index, fs_manager, token_counter, f"file{i}.md", content
        )

    managers = _build_managers(
        fs_manager, metadata_index, optimization_config, summarization_engine
    )

    result = json.loads(
        await summarize_content_impl(managers, None, 0.5, "extract_key_sections")
    )

    assert result["status"] == expected_status
    assert result["files_summarized"] == total
    assert result["files_meeting_target"] == hits
