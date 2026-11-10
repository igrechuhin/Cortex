"""Bounded Swift build budgets for selected read-only source checks."""

import os


def swift_build_timeout(timeout: int | None = None) -> int:
    """Use BUILD_TIMEOUT, then the gate budget, then a 300-second default.

    BUILD_TIMEOUT matches Synapse build scripts. Invalid budgets fail closed
    rather than silently disabling the deadline or ignoring configuration.
    """
    configured = os.environ.get("BUILD_TIMEOUT")
    budget = int(configured) if configured is not None else timeout
    if budget is None:
        return 300
    if isinstance(budget, bool) or budget <= 0:
        raise ValueError("Swift build timeout must be a positive integer")
    return budget
