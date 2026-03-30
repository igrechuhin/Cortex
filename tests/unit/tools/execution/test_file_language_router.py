"""Umbrella re-export for file_language_router tests.

The test suite has been split into focused modules to stay under the 400-line
file limit. This file re-exports all tests so existing test-runner invocations
that target this path continue to work.
"""

from tests.unit.tools.execution.test_file_language_router_dispatch import *  # noqa: F401,F403
from tests.unit.tools.execution.test_file_language_router_parsing import *  # noqa: F401,F403
from tests.unit.tools.execution.test_file_language_router_routing import *  # noqa: F401,F403
