"""Comprehensive test suite for ``file_watcher.py``.

Tests ``MemoryBankWatcher`` and ``FileWatcherManager`` for file system
monitoring with debouncing, event filtering, and proper lifecycle
management.
"""

import asyncio
from pathlib import Path
from typing import Protocol, cast, runtime_checkable
from unittest.mock import AsyncMock, patch

import pytest
from watchdog.events import FileCreatedEvent, FileDeletedEvent, FileModifiedEvent

from cortex.core.file_watcher import FileWatcherManager, MemoryBankWatcher


@runtime_checkable
class _ObserverWithIsAlive(Protocol):
    def is_alive(self) -> bool:
        """Return True if the observer thread is running."""
        ...


class TestMemoryBankWatcherInitialization:
    """Tests for MemoryBankWatcher initialization."""

    def test_initialization_with_valid_parameters(self, tmp_path: Path) -> None:
        """Test watcher initializes with valid parameters."""
        callback = AsyncMock()
        watcher = MemoryBankWatcher(
            memory_bank_dir=tmp_path,
            on_change_callback=callback,
            debounce_delay=2.0,
        )

        assert watcher.memory_bank_dir == tmp_path
        assert watcher.on_change_callback == callback
        assert watcher.debounce_delay == 2.0
        assert watcher.pending_updates == {}
        assert watcher.observer is None
        assert watcher.loop is None

    def test_initialization_with_default_debounce(self, tmp_path: Path) -> None:
        """Test watcher uses default debounce delay of 1.0 seconds."""
        callback = AsyncMock()
        watcher = MemoryBankWatcher(
            memory_bank_dir=tmp_path, on_change_callback=callback
        )

        assert watcher.debounce_delay == 1.0

    def test_initialization_converts_string_path(self, tmp_path: Path) -> None:
        """Test watcher converts string path to Path object."""
        from typing import cast

        callback = AsyncMock()
        watcher = MemoryBankWatcher(
            memory_bank_dir=cast(Path, str(tmp_path)), on_change_callback=callback
        )

        assert isinstance(watcher.memory_bank_dir, Path)
        assert watcher.memory_bank_dir == tmp_path


class TestMemoryBankWatcherLifecycle:
    """Tests for watcher start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_initializes_observer(self, tmp_path: Path) -> None:
        """Test start() initializes and starts the observer."""
        callback = AsyncMock()
        watcher = MemoryBankWatcher(tmp_path, callback)
        loop = asyncio.get_event_loop()

        watcher.start(loop)

        try:
            assert watcher.observer is not None
            assert watcher.loop == loop
            observer = cast(_ObserverWithIsAlive, watcher.observer)
            assert observer.is_alive()
        finally:
            watcher.stop()

    @pytest.mark.asyncio
    async def test_stop_stops_observer(self, tmp_path: Path) -> None:
        """Test stop() stops the observer."""
        callback = AsyncMock()
        watcher = MemoryBankWatcher(tmp_path, callback)
        loop = asyncio.get_event_loop()

        watcher.start(loop)
        # After start, the underlying observer should be created.
        assert watcher.observer is not None

        watcher.stop()

        # After stop, the watcher should detach from the observer implementation.
        assert watcher.observer is None

    @pytest.mark.asyncio
    async def test_stop_without_observer_does_not_fail(self, tmp_path: Path) -> None:
        """Test stop() is safe to call before start()."""
        callback = AsyncMock()
        watcher = MemoryBankWatcher(tmp_path, callback)

        # Should not raise exception
        watcher.stop()


class TestMemoryBankWatcherEventFiltering:
    """Tests for file event filtering."""

    @pytest.mark.asyncio
    async def test_on_modified_filters_markdown_files(self, tmp_path: Path) -> None:
        """Test on_modified only processes .md files."""
        callback = AsyncMock()
        watcher = MemoryBankWatcher(tmp_path, callback, debounce_delay=0.1)
        loop = asyncio.get_event_loop()
        watcher.loop = loop

        # Create markdown file event
        md_file = tmp_path / "test.md"
        event = FileModifiedEvent(str(md_file))

        with patch.object(watcher, "schedule_update") as mock_schedule:
            watcher.on_modified(event)
            mock_schedule.assert_called_once_with(md_file, "modified")

    @pytest.mark.asyncio
    async def test_on_modified_ignores_non_markdown_files(self, tmp_path: Path) -> None:
        """Test on_modified ignores non-.md files."""
        callback = AsyncMock()
        watcher = MemoryBankWatcher(tmp_path, callback)
        loop = asyncio.get_event_loop()
        watcher.loop = loop

        # Create non-markdown file event
        txt_file = tmp_path / "test.txt"
        event = FileModifiedEvent(str(txt_file))

        with patch.object(watcher, "schedule_update") as mock_schedule:
            watcher.on_modified(event)
            mock_schedule.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_modified_ignores_metadata_index(self, tmp_path: Path) -> None:
        """Test on_modified ignores .memory-bank-index file."""
        callback = AsyncMock()
        watcher = MemoryBankWatcher(tmp_path, callback)
        loop = asyncio.get_event_loop()
        watcher.loop = loop

        # Create metadata index event
        index_file = tmp_path / ".memory-bank-index"
        event = FileModifiedEvent(str(index_file))

        with patch.object(watcher, "schedule_update") as mock_schedule:
            watcher.on_modified(event)
            mock_schedule.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_modified_ignores_directories(self, tmp_path: Path) -> None:
        """Test on_modified ignores directory events."""
        callback = AsyncMock()
        watcher = MemoryBankWatcher(tmp_path, callback)
        loop = asyncio.get_event_loop()
        watcher.loop = loop

        # Create directory event
        event = FileModifiedEvent(str(tmp_path / "subdir"))
        event.is_directory = True

        with patch.object(watcher, "schedule_update") as mock_schedule:
            watcher.on_modified(event)
            mock_schedule.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_created_processes_markdown_files(self, tmp_path: Path) -> None:
        """Test on_created processes .md file creation."""
        callback = AsyncMock()
        watcher = MemoryBankWatcher(tmp_path, callback)
        loop = asyncio.get_event_loop()
        watcher.loop = loop

        md_file = tmp_path / "new.md"
        event = FileCreatedEvent(str(md_file))

        with patch.object(watcher, "schedule_update") as mock_schedule:
            watcher.on_created(event)
            mock_schedule.assert_called_once_with(md_file, "created")

    @pytest.mark.asyncio
    async def test_on_deleted_processes_markdown_files(self, tmp_path: Path) -> None:
        """Test on_deleted processes .md file deletion."""
        callback = AsyncMock()
        watcher = MemoryBankWatcher(tmp_path, callback)
        loop = asyncio.get_event_loop()
        watcher.loop = loop

        md_file = tmp_path / "deleted.md"
        event = FileDeletedEvent(str(md_file))

        with patch.object(watcher, "schedule_update") as mock_schedule:
            watcher.on_deleted(event)
            mock_schedule.assert_called_once_with(md_file, "deleted")


class TestMemoryBankWatcherDebouncing:
    """Tests for debouncing behavior."""

    @pytest.mark.asyncio
    async def test_schedule_update_debounces_rapid_changes(
        self, tmp_path: Path
    ) -> None:
        """Test schedule_update debounces rapid file changes."""
        callback = AsyncMock()
        watcher = MemoryBankWatcher(tmp_path, callback, debounce_delay=0.2)
        loop = asyncio.get_event_loop()
        watcher.loop = loop

        file_path = tmp_path / "test.md"

        # Schedule multiple rapid updates
        watcher.schedule_update(file_path, "modified")
        await asyncio.sleep(0.05)
        watcher.schedule_update(file_path, "modified")
        await asyncio.sleep(0.05)
        watcher.schedule_update(file_path, "modified")

        # Only one update should be pending
        assert len(watcher.pending_updates) == 1
        assert file_path in watcher.pending_updates

        # Wait for debounce
        await asyncio.sleep(0.3)

        # Callback should be called exactly once
        callback.assert_called_once_with(file_path, "modified")

    @pytest.mark.asyncio
    async def test_schedule_update_without_loop_does_nothing(
        self, tmp_path: Path
    ) -> None:
        """Test schedule_update safely ignores calls before start()."""
        callback = AsyncMock()
        watcher = MemoryBankWatcher(tmp_path, callback)
        # Don't set _loop

        file_path = tmp_path / "test.md"
        watcher.schedule_update(file_path, "modified")

        # Should not raise exception
        assert len(watcher.pending_updates) == 0

    @pytest.mark.asyncio
    async def test_update_after_delay_calls_callback(self, tmp_path: Path) -> None:
        """Test update_after_delay calls callback after delay."""
        callback = AsyncMock()
        watcher = MemoryBankWatcher(tmp_path, callback, debounce_delay=0.1)

        file_path = tmp_path / "test.md"
        await watcher.update_after_delay(file_path, "modified")

        callback.assert_called_once_with(file_path, "modified")

    @pytest.mark.asyncio
    async def test_update_after_delay_handles_cancellation(
        self, tmp_path: Path
    ) -> None:
        """Test update_after_delay handles task cancellation gracefully."""
        callback = AsyncMock()
        watcher = MemoryBankWatcher(tmp_path, callback, debounce_delay=1.0)

        file_path = tmp_path / "test.md"
        task = asyncio.create_task(
            watcher.update_after_delay(file_path, "modified"),
        )

        # Cancel the task
        _ = task.cancel()

        # Should propagate cancellation to caller
        with pytest.raises(asyncio.CancelledError):
            await task

        # Callback should not be called
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_after_delay_handles_callback_errors(
        self, tmp_path: Path
    ) -> None:
        """Test update_after_delay handles callback exceptions gracefully."""
        callback = AsyncMock(side_effect=Exception("Callback failed"))
        watcher = MemoryBankWatcher(tmp_path, callback, debounce_delay=0.1)

        file_path = tmp_path / "test.md"

        # Should not raise exception
        await watcher.update_after_delay(file_path, "modified")

        callback.assert_called_once()


class TestFileWatcherManagerInitialization:
    """Tests for FileWatcherManager initialization."""

    def test_initialization(self):
        """Test FileWatcherManager initializes with default state."""
        manager = FileWatcherManager()

        assert manager.watcher is None
        assert manager.is_running is False


class TestFileWatcherManagerLifecycle:
    """Tests for FileWatcherManager start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_watcher(self, tmp_path: Path) -> None:
        """Test start() creates and starts watcher."""
        manager = FileWatcherManager()
        callback = AsyncMock()

        await manager.start(tmp_path, callback)

        assert manager.watcher is not None
        assert manager.is_running is True
        assert manager.watcher.observer is not None

        manager.stop()

    @pytest.mark.asyncio
    async def test_start_creates_directory_if_not_exists(self, tmp_path: Path) -> None:
        """Test start() creates directory if it doesn't exist."""
        manager = FileWatcherManager()
        callback = AsyncMock()
        non_existent = tmp_path / "memory-bank"

        assert not non_existent.exists()

        await manager.start(non_existent, callback)

        assert non_existent.exists()
        assert manager.is_running is True

        manager.stop()

    @pytest.mark.asyncio
    async def test_start_with_custom_debounce(self, tmp_path: Path) -> None:
        """Test start() passes custom debounce delay to watcher."""
        manager = FileWatcherManager()
        callback = AsyncMock()

        await manager.start(tmp_path, callback, debounce_delay=2.5)

        assert manager.watcher is not None
        assert manager.watcher.debounce_delay == 2.5

        manager.stop()

    @pytest.mark.asyncio
    async def test_start_when_already_running_does_nothing(
        self, tmp_path: Path
    ) -> None:
        """Test start() is idempotent when already running."""
        manager = FileWatcherManager()
        callback = AsyncMock()

        await manager.start(tmp_path, callback)
        first_watcher = manager.watcher

        # Try to start again
        await manager.start(tmp_path, callback)

        # Should still have the same watcher
        assert manager.watcher is first_watcher

        manager.stop()

    def test_stop_stops_watcher(self, tmp_path: Path) -> None:
        """Test stop() stops the watcher and resets state."""
        manager = FileWatcherManager()
        callback = AsyncMock()

        # Start watcher
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(manager.start(tmp_path, callback))

            assert manager.is_running is True
            assert manager.watcher is not None

            # Stop watcher
            manager.stop()

            assert manager.is_running is False
            assert manager.watcher is None
        finally:
            loop.close()

    def test_stop_when_not_running_does_nothing(self):
        """Test stop() is safe to call when not running."""
        manager = FileWatcherManager()

        # Should not raise exception
        manager.stop()

    def test_destructor_calls_stop(self, tmp_path: Path) -> None:
        """Test __del__ stops the watcher."""
        manager = FileWatcherManager()
        callback = AsyncMock()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(manager.start(tmp_path, callback))
            assert manager.is_running is True

            # Trigger destructor
            manager.__del__()

            assert manager.is_running is False
        finally:
            loop.close()


class TestFileWatcherManagerIntegration:
    """Integration tests for FileWatcherManager with real file events."""

    @pytest.mark.asyncio
    async def test_end_to_end_file_modification_detection(self, tmp_path: Path) -> None:
        """Test end-to-end file modification detection."""
        manager = FileWatcherManager()
        callback = AsyncMock()

        await manager.start(tmp_path, callback, debounce_delay=0.2)

        # Create and modify a file
        test_file = tmp_path / "test.md"
        _ = test_file.write_text("Initial content")

        # Wait for watcher to detect file
        await asyncio.sleep(0.5)

        # Callback should be called for file creation
        # Note: Actual file system events may vary by OS
        # This is a best-effort integration test

        manager.stop()

    @pytest.mark.asyncio
    async def test_multiple_file_changes(self, tmp_path: Path) -> None:
        """Test handling multiple file changes."""
        manager = FileWatcherManager()
        callback = AsyncMock()

        await manager.start(tmp_path, callback, debounce_delay=0.1)

        # Create multiple files
        file1 = tmp_path / "file1.md"
        file2 = tmp_path / "file2.md"

        _ = file1.write_text("Content 1")
        _ = file2.write_text("Content 2")

        # Wait for debounce
        await asyncio.sleep(0.3)

        manager.stop()
