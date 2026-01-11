"""File system monitoring using watchdog for external change detection."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from concurrent.futures import Future
from pathlib import Path
from typing import Protocol, override

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer


class ObserverProtocol(Protocol):
    """Protocol for watchdog Observer interface."""

    def stop(self) -> None:
        """Stop the observer."""
        ...

    def join(self, timeout: float | None = None) -> None:
        """Wait for the observer thread to finish."""
        ...

    def schedule(
        self,
        event_handler: FileSystemEventHandler,
        path: str,
        *,
        recursive: bool = False,
        event_filter: list[type[FileSystemEvent]] | None = None,
    ) -> object:
        """Schedule watching a path."""
        ...

    def start(self) -> None:
        """Start the observer."""
        ...


class MemoryBankWatcher(FileSystemEventHandler):
    """
    Monitors memory-bank/ directory for external changes.
    Updates metadata index when files are modified outside MCP.
    """

    def __init__(
        self,
        memory_bank_dir: Path,
        on_change_callback: Callable[[Path, str], Awaitable[None]],
        debounce_delay: float = 1.0,
    ):
        """
        Initialize file watcher.

        Args:
            memory_bank_dir: Directory to watch
            on_change_callback: Async callback function to call on changes
                                Signature: async def callback(file_path: Path, event_type: str)
            debounce_delay: Delay in seconds before processing change (default: 1.0)
        """
        super().__init__()
        self.memory_bank_dir: Path = Path(memory_bank_dir)
        self.on_change_callback: Callable[[Path, str], Awaitable[None]] = (
            on_change_callback
        )
        self.debounce_delay: float = debounce_delay
        self.pending_updates: dict[Path, Future[None]] = {}
        self.observer: ObserverProtocol | None = None
        self.loop: asyncio.AbstractEventLoop | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """
        Start watching the directory.

        Args:
            loop: Event loop to use for async callbacks
        """
        self.loop = loop
        observer = Observer()
        _ = observer.schedule(self, str(self.memory_bank_dir), recursive=False)
        observer.start()
        self.observer = observer

    def stop(self):
        """Stop watching the directory."""
        if self.observer is not None:
            self.observer.stop()
            self.observer.join(timeout=5)
            self.observer = None

    @override
    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if isinstance(event, FileModifiedEvent) and not event.is_directory:
            file_path = Path(str(event.src_path))
            if file_path.suffix == ".md" and file_path.name != "index.json":
                self.schedule_update(file_path, "modified")

    @override
    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if isinstance(event, FileCreatedEvent) and not event.is_directory:
            file_path = Path(str(event.src_path))
            if file_path.suffix == ".md":
                self.schedule_update(file_path, "created")

    @override
    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion events."""
        if isinstance(event, FileDeletedEvent) and not event.is_directory:
            file_path = Path(str(event.src_path))
            if file_path.suffix == ".md":
                self.schedule_update(file_path, "deleted")

    def schedule_update(self, file_path: Path, event_type: str):
        """
        Schedule a debounced update for a file.

        Args:
            file_path: Path to file that changed
            event_type: Type of event (modified, created, deleted)
        """
        if not self.loop:
            return

        # Cancel pending update if exists
        if file_path in self.pending_updates:
            _ = self.pending_updates[file_path].cancel()

        # Schedule new update
        future = asyncio.run_coroutine_threadsafe(
            self.update_after_delay(file_path, event_type), self.loop
        )
        self.pending_updates[file_path] = future

    async def update_after_delay(self, file_path: Path, event_type: str):
        """
        Wait for debounce delay, then trigger callback.

        Args:
            file_path: Path to file that changed
            event_type: Type of event
        """
        try:
            await asyncio.sleep(self.debounce_delay)

            # Call the callback
            await self.on_change_callback(file_path, event_type)

            # Remove from pending updates
            if file_path in self.pending_updates:
                del self.pending_updates[file_path]

        except asyncio.CancelledError:
            # Update was cancelled - that's fine
            pass
        except Exception as e:
            # Log error but don't crash
            print(f"Error processing file change {file_path}: {e}")


class FileWatcherManager:
    """
    High-level manager for file watching with proper lifecycle management.
    """

    def __init__(self):
        """Initialize file watcher manager."""
        self.watcher: MemoryBankWatcher | None = None
        self.is_running: bool = False

    async def start(
        self,
        memory_bank_dir: Path,
        on_change_callback: Callable[[Path, str], Awaitable[None]],
        debounce_delay: float = 1.0,
    ):
        """
        Start file watching.

        Args:
            memory_bank_dir: Directory to watch
            on_change_callback: Async callback for changes
            debounce_delay: Debounce delay in seconds
        """
        if self.is_running:
            return

        if not memory_bank_dir.exists():
            memory_bank_dir.mkdir(parents=True, exist_ok=True)

        self.watcher = MemoryBankWatcher(
            memory_bank_dir, on_change_callback, debounce_delay
        )

        loop = asyncio.get_event_loop()
        self.watcher.start(loop)
        self.is_running = True

    def stop(self):
        """Stop file watching."""
        if self.watcher and self.is_running:
            self.watcher.stop()
            self.is_running = False
            self.watcher = None

    def __del__(self):
        """Cleanup on deletion."""
        self.stop()
