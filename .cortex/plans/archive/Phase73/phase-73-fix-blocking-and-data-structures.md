# Phase 73: Fix Blocking Event Loop and O(n) Data Structures

## Status

PENDING

## Goal

Fix three performance issues that cause event loop blocking and algorithmic inefficiency: `time.sleep()` in async code, O(n) LRU cache eviction, and O(n) BFS queue operations.

## Context

The code review (2026-03-04) identified three performance issues:

- **HIGH**: `time.sleep()` blocks the async event loop in `core/token_counter.py`
- **HIGH**: LRU Cache uses O(n) `list.remove()` + `list.append()` instead of O(1) `OrderedDict` in `core/cache.py`
- **HIGH**: BFS queues use `list.pop(0)` (O(n)) instead of `deque.popleft()` (O(1)) in `core/graph_algorithms.py`

## Approach

Direct replacements with correct data structures and async primitives.

## Implementation Steps

### Step 1: Replace time.sleep() with asyncio.sleep()

- In `core/token_counter.py`, replace `time.sleep()` with `await asyncio.sleep()`
- Ensure the calling function is async; update call chain if needed

### Step 2: Replace LRU Cache list with OrderedDict

- In `core/cache.py`, replace the list-based LRU tracking with `collections.OrderedDict`
- Use `move_to_end()` for cache hits (O(1))
- Use `popitem(last=False)` for eviction (O(1))

### Step 3: Replace list.pop(0) with deque.popleft()

- In `core/graph_algorithms.py`, replace BFS queue `list` with `collections.deque`
- Replace `.pop(0)` with `.popleft()`
- Replace `.append()` with `.append()` (same for deque)

### Step 4: Audit shared mutable state for lock requirements

- **Systematically audit** all module-level and instance-level mutable state that is accessed during request handling:
  - `token_counter.py`: `self._cache` dict — is it safe under concurrent async access?
  - `transclusion_engine.py`: cache dict — accessed from multiple tool handlers?
  - `advanced_cache.py` / `cache_warming.py`: shared cache state
  - Any module-level dicts/lists that accumulate state across requests
- For each mutable data structure, determine:
  - Is it read-only after init? → No lock needed
  - Is it mutated during async request handling? → Needs `asyncio.Lock`
  - Is it a cache with set/get from concurrent coroutines? → Needs lock or atomic update pattern
- **IMPORTANT**: A previous agent assessment concluded "no additional locks needed" after a shallow review. This step requires reading each module's `__init__` and mutating methods, not just scanning class names.

### Step 5: Add tests

- Test token counter async behavior (no event loop blocking)
- Test LRU cache correctness after OrderedDict migration
- Test BFS correctness after deque migration
- Test any newly-added locks with concurrent coroutine scenarios
- Benchmark before/after for cache operations

## Dependencies

None.

## Success Criteria

- Zero `time.sleep()` calls in async code paths
- All cache operations are O(1)
- All BFS queue operations are O(1)
- Shared mutable state either confirmed safe or protected with `asyncio.Lock`
- All existing tests pass
- 95%+ test coverage for changed code

## Testing Strategy

- **Unit Tests**: Cache get/set/evict with OrderedDict, BFS traversal with deque, async sleep behavior, concurrent cache access with asyncio.Lock
- **Edge Cases**: Empty cache, full cache eviction, single-node BFS, large graph BFS, concurrent cache access from multiple coroutines
- **Regression**: All existing cache and graph algorithm tests pass
- **Coverage Target**: 95%+ for modified modules

## Risks & Mitigation

- **Risk**: OrderedDict migration may change cache iteration order in edge cases
- **Mitigation**: OrderedDict maintains insertion order same as list; verify with existing tests
- **Risk**: Shared-state audit concludes "no locks needed" prematurely
- **Mitigation**: Step 4 requires reading actual mutating methods, not just class-level declarations; document rationale for each "no lock needed" decision

## Timeline

Low effort (4-6h total for all three fixes)
