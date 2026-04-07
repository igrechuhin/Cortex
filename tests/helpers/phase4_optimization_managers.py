"""Typed Phase 4 mock managers for optimization tests (split for function-length limits)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from cortex.core.models import DetailedFileMetadata
from cortex.managers.types import ManagersDict
from tests.helpers.fixture_validator import validate_optimization_config_mock
from tests.helpers.managers import make_test_managers


def _build_optimization_config_mock() -> MagicMock:
    optimization_config = MagicMock()
    optimization_config.get_token_budget.return_value = 10000
    optimization_config.get_max_token_budget.return_value = 100000
    optimization_config.get_reserve_for_response.return_value = 10000
    optimization_config.get_priority_order.return_value = ["file1.md", "file2.md"]
    optimization_config.get_mandatory_files.return_value = ["file1.md"]
    optimization_config.is_summarization_enabled.return_value = True
    optimization_config.is_optimization_enabled.return_value = True
    optimization_config.get_summarization_target_reduction.return_value = 0.5
    optimization_config.get_summarization_strategy.return_value = "extract_key_sections"
    validation = validate_optimization_config_mock(optimization_config)
    if not validation.valid:
        pytest.fail(validation.message)
    return optimization_config


def _build_context_optimizer_mock(mock_optimization_result: MagicMock) -> MagicMock:
    context_optimizer = MagicMock()
    context_optimizer.optimize_context = AsyncMock(
        return_value=mock_optimization_result
    )
    return context_optimizer


def _build_progressive_loader_mock(mock_loaded_content: list[Any]) -> MagicMock:
    progressive_loader = MagicMock()
    progressive_loader.load_by_priority = AsyncMock(return_value=mock_loaded_content)
    progressive_loader.load_by_dependencies = AsyncMock(
        return_value=mock_loaded_content
    )
    progressive_loader.load_by_relevance = AsyncMock(return_value=mock_loaded_content)
    return progressive_loader


def _build_summarization_engine_mock() -> MagicMock:
    summarization_engine = MagicMock()
    summarization_engine.summarize_file = AsyncMock(
        return_value={
            "original_tokens": 1000,
            "summary_tokens": 500,
            "reduction": 0.5,
            "summary": "Test summary",
            "strategy": "extract_key_sections",
            "sections_kept": 0,
            "sections_removed": 0,
        }
    )
    return summarization_engine


def _build_relevance_scorer_mock() -> MagicMock:
    relevance_scorer = MagicMock()
    relevance_scorer.score_files = AsyncMock(
        return_value={
            "file1.md": {"total_score": 0.9, "keyword_score": 0.8},
            "file2.md": {"total_score": 0.7, "keyword_score": 0.6},
        }
    )
    relevance_scorer.score_sections = AsyncMock(
        return_value=[
            MagicMock(section="Section 1", title=None, score=0.9, reason="match"),
            MagicMock(section="Section 2", title=None, score=0.8, reason="match"),
        ]
    )
    return relevance_scorer


def _build_metadata_index_mock() -> MagicMock:
    file_metadata_model = DetailedFileMetadata(
        path="/mock/memory-bank/file.md",
        exists=True,
        size_bytes=100,
        token_count=1000,
        token_model="cl100k_base",
        last_modified="2026-01-01T00:00:00",
        content_hash="mock",
    )
    metadata_index = MagicMock()
    metadata_index.list_all_files = AsyncMock(return_value=["file1.md", "file2.md"])
    metadata_index.get_file_metadata = AsyncMock(return_value=file_metadata_model)
    metadata_index.memory_bank_dir = Path("/mock/memory-bank")
    return metadata_index


def build_phase4_mock_managers(
    mock_optimization_result: MagicMock, mock_loaded_content: list[Any]
) -> ManagersDict:
    """Create typed mock managers container for Phase 4 optimization tests."""
    optimization_config = _build_optimization_config_mock()
    context_optimizer = _build_context_optimizer_mock(mock_optimization_result)
    progressive_loader = _build_progressive_loader_mock(mock_loaded_content)
    summarization_engine = _build_summarization_engine_mock()
    relevance_scorer = _build_relevance_scorer_mock()
    metadata_index = _build_metadata_index_mock()
    fs_manager = MagicMock()
    fs_manager.read_file = AsyncMock(return_value=("Test content", None))
    return make_test_managers(
        optimization_config=optimization_config,
        context_optimizer=context_optimizer,
        progressive_loader=progressive_loader,
        summarization_engine=summarization_engine,
        relevance_scorer=relevance_scorer,
        index=metadata_index,
        fs=fs_manager,
    )
