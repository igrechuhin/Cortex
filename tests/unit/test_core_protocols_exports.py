"""Guard that the protocols package re-exports exactly what it defines."""

import cortex.core.protocols as protocols


def test_all_entries_resolve_and_match_namespace() -> None:
    """__all__ must list every imported protocol, and nothing stale."""
    # Arrange
    exported = set(protocols.__all__)

    # Act
    in_namespace = {
        name
        for name in vars(protocols)
        if not name.startswith("_") and name.endswith("Protocol")
    }

    # Assert
    assert exported == in_namespace
    assert len(protocols.__all__) == len(exported)
