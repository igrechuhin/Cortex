"""Unit tests for LazyManager."""

import asyncio

import pytest

from cortex.managers.lazy_manager import LazyManager


@pytest.mark.asyncio
async def test_lazy_manager_initialization():
    """Test lazy manager initializes on first access."""
    call_count = 0

    async def factory():
        nonlocal call_count
        call_count += 1
        return "initialized"

    lazy = LazyManager(factory, name="test")

    # Not initialized yet
    assert not lazy.is_initialized
    assert call_count == 0

    # First access initializes
    result1 = await lazy.get()
    assert result1 == "initialized"
    assert lazy.is_initialized
    assert call_count == 1

    # Second access reuses instance
    result2 = await lazy.get()
    assert result2 == "initialized"
    assert call_count == 1  # Not called again


@pytest.mark.asyncio
async def test_lazy_manager_concurrent_access():
    """Test lazy manager handles concurrent initialization."""
    call_count = 0

    async def factory():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # Simulate work
        return f"initialized-{call_count}"

    lazy = LazyManager(factory, name="test")

    # Multiple concurrent accesses
    results = await asyncio.gather(
        lazy.get(),
        lazy.get(),
        lazy.get(),
    )

    # Should only initialize once
    assert call_count == 1
    assert all(r == results[0] for r in results)


@pytest.mark.asyncio
async def test_lazy_manager_invalidate():
    """Test lazy manager invalidation."""
    call_count = 0

    async def factory():
        nonlocal call_count
        call_count += 1
        return f"initialized-{call_count}"

    lazy = LazyManager(factory, name="test")

    # First initialization
    result1 = await lazy.get()
    assert result1 == "initialized-1"
    assert call_count == 1

    # Invalidate
    await lazy.invalidate()
    assert not lazy.is_initialized

    # Second initialization after invalidation
    result2 = await lazy.get()
    assert result2 == "initialized-2"
    assert call_count == 2


@pytest.mark.asyncio
async def test_lazy_manager_name_property():
    """Test lazy manager name property."""
    lazy = LazyManager(lambda: asyncio.sleep(0), name="test_manager")
    assert lazy.name == "test_manager"


@pytest.mark.asyncio
async def test_lazy_manager_with_exception():
    """Test lazy manager handles initialization exceptions."""

    async def factory():
        raise ValueError("Initialization failed")

    lazy = LazyManager(factory, name="test")

    # Should propagate exception
    with pytest.raises(ValueError, match="Initialization failed"):
        await lazy.get()

    # Should not be marked as initialized
    assert not lazy.is_initialized

    # Should retry on next access
    with pytest.raises(ValueError, match="Initialization failed"):
        await lazy.get()


@pytest.mark.asyncio
async def test_lazy_manager_with_complex_type():
    """Test lazy manager with complex return type."""

    class ComplexManager:
        def __init__(self, value: int):
            self.value = value

        async def process(self) -> int:
            return self.value * 2

    async def factory():
        return ComplexManager(42)

    lazy: LazyManager[ComplexManager] = LazyManager(factory, name="complex")

    # Get and use the manager
    manager = await lazy.get()
    assert isinstance(manager, ComplexManager)
    assert manager.value == 42
    assert await manager.process() == 84

    # Verify caching
    manager2 = await lazy.get()
    assert manager2 is manager
