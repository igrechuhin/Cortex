"""Type definitions for test helpers.

This module provides type aliases for common test patterns to avoid
using dict[str, object] throughout test files.

Note: dict[str, object] is acceptable in tests when:
1. Testing JSON parsing boundaries (simulating raw JSON data)
2. Testing backward compatibility with legacy dict-based APIs
3. Testing error handling for malformed input

For new test code, prefer using Pydantic models directly.
"""

from unittest.mock import AsyncMock, MagicMock

# Type alias for mock managers dictionary used in tests.
# Tests populate this with MagicMock or AsyncMock instances.
# Note: We use MagicMock | AsyncMock | object because mock managers don't implement
# the full protocol and type checkers would otherwise complain about incompatible types.
MockManagersDict = dict[str, MagicMock | AsyncMock]

# Type alias for test managers dictionary.
# This is a permissive type for tests that need to pass mock managers
# to functions expecting ManagersDict. Using object is acceptable in tests
# because we're testing behavior, not type safety.
TestManagersDict = dict[str, MagicMock | AsyncMock | object]

# Type alias for raw JSON data in tests.
# Used when testing JSON parsing boundaries where data comes from json.load().
# This is acceptable because JSON can contain arbitrary nested structures.
RawJSONDict = dict[str, object]

# Type alias for raw JSON list data in tests.
RawJSONList = list[object]
