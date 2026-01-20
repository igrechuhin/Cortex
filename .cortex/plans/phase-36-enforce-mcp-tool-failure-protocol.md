# Phase 36: Enforce MCP Tool Failure Protocol

**Status**: PLANNING  
**Priority**: ASAP (Blocker)  
**Created**: 2026-01-16  
**Target Completion**: 2026-01-17

## Goal

Enforce mandatory stopping when Cortex MCP tools fail during commit procedure, ensuring agents cannot continue with workarounds or fallbacks. Add automated detection and enforcement mechanisms to prevent protocol violations.

## Context

**Problem**: During commit procedure execution, when `execute_pre_commit_checks()` MCP tool failed with JSON parsing error, the agent:

1. Did NOT stop immediately (violated protocol)
2. Attempted workaround by calling function directly via Python (violated "DO NOT attempt retry or use fallback methods")
3. Tried to continue fixing errors manually instead of stopping
4. Only created investigation plan after user explicitly asked

**Root Cause**: The MCP Tool Failure protocol exists in commit.md (lines 827-847) but:

- Protocol is not automatically enforced
- No validation checks prevent agents from continuing
- No automated detection of protocol violations
- Agents can bypass the protocol by using workarounds

**Impact**:

- Commit procedure can proceed with broken tools, hiding critical issues
- Tool failures are not properly tracked or investigated
- Violations waste time and prevent proper issue resolution
- User must manually catch and enforce protocol compliance

**Affected Steps**: All commit procedure steps that use MCP tools, especially:

- Step 0: Fix Errors (`execute_pre_commit_checks`)
- Step 1: Formatting (`execute_pre_commit_checks`)
- Step 1.5: Markdown Linting (`fix_markdown_lint`)
- Step 2: Type Checking (`execute_pre_commit_checks`) - **#2**
- Step 3: Code Quality Checks (`execute_pre_commit_checks`)
- Step 4: Test Execution (`execute_pre_commit_checks`) - **#4**
- Step 5: Memory Bank Update (`manage_file`)
- Step 6: Roadmap Update (`manage_file`) - **#6**
- Step 9: Memory Bank Timestamp Validation (`validate`)
- Step 10: Roadmap Synchronization Validation (`validate`)

## Requirements

### Functional Requirements

1. **Automatic Protocol Enforcement**:
   - Detect MCP tool failures (crashes, disconnects, unexpected behavior, JSON parsing errors)
   - Immediately stop commit procedure execution
   - Prevent any workarounds or fallback methods
   - Block all subsequent steps until tool issue is resolved

2. **Investigation Plan Creation**:
   - Automatically create investigation plan when MCP tool fails
   - Use `create-plan.md` prompt to generate plan
   - Include tool name, error details, step where failure occurred
   - Add plan to roadmap under "Blockers (ASAP Priority)"

3. **User Notification**:
   - Provide immediate summary to user when tool fails
   - Include: tool name, error description, impact, fix recommendation, plan location
   - Mark as FIX-ASAP priority
   - Clear next steps for user

4. **Validation and Detection**:
   - Detect protocol violations (attempts to use workarounds)
   - Prevent fallback method usage when MCP tool fails
   - Track tool failures for analysis
   - Ensure investigation plans are created before any continuation

### Technical Requirements

1. **Error Detection**:
   - Detect JSON parsing errors from MCP tool calls
   - Detect connection errors (disconnects, timeouts)
   - Detect unexpected behavior (wrong return types, malformed responses)
   - Distinguish between tool failures and expected errors (e.g., validation failures)

2. **Protocol Enforcement**:
   - Add validation checks after each MCP tool call
   - Block commit procedure if tool failure detected
   - Prevent fallback method execution
   - Ensure investigation plan creation is mandatory

3. **Integration Points**:
   - Integrate with commit procedure steps
   - Hook into MCP tool wrapper (`mcp_tool_wrapper`)
   - Add validation in commit.md command execution
   - Ensure all Cortex MCP tools are covered

## Approach

### Strategy

1. **Add Protocol Enforcement Layer**:
   - Create `MCPToolFailureHandler` class to centralize failure detection and handling
   - Integrate with `mcp_tool_wrapper` decorator to catch failures
   - Add validation checks in commit procedure after each MCP tool call

2. **Enhance Error Detection**:
   - Detect JSON parsing errors (malformed JSON responses)
   - Detect connection errors (disconnects, timeouts)
   - Detect unexpected behavior (wrong return types, missing fields)
   - Distinguish tool failures from expected errors

3. **Automate Investigation Plan Creation**:
   - Create helper function to automatically generate investigation plans
   - Use `create-plan.md` prompt structure
   - Automatically add to roadmap as blocker

4. **Add Validation Checks**:
   - Add explicit checks after each MCP tool call in commit procedure
   - Verify tool response is valid before proceeding
   - Block commit procedure if validation fails

5. **Prevent Workarounds**:
   - Add checks to prevent fallback method usage
   - Block direct Python calls when MCP tool fails
   - Ensure protocol is followed automatically

## Implementation Steps

### Step 1: Create MCP Tool Failure Handler

1. **Create `MCPToolFailureHandler` class**:
   - Location: `src/cortex/core/mcp_failure_handler.py`
   - Responsibilities:
     - Detect MCP tool failures (JSON parsing, connection, unexpected behavior)
     - Create investigation plans automatically
     - Add plans to roadmap as blockers
     - Provide user notifications
   - Methods:
     - `detect_failure(error, tool_name, step_name) -> bool`
     - `handle_failure(tool_name, error, step_name) -> None`
     - `create_investigation_plan(tool_name, error, step_name) -> str`
     - `add_to_roadmap(plan_path, tool_name) -> None`
     - `notify_user(tool_name, error, plan_path) -> None`

2. **Integrate with MCP Tool Wrapper**:
   - Update `mcp_tool_wrapper` decorator in `mcp_stability.py`
   - Catch exceptions and detect failures
   - Call `MCPToolFailureHandler.handle_failure()` on failure
   - Prevent tool execution from continuing

3. **Add Failure Detection Logic**:
   - Detect JSON parsing errors (malformed JSON, unexpected structure)
   - Detect connection errors (disconnects, timeouts)
   - Detect unexpected behavior (wrong return types, missing fields)
   - Return failure status to handler

### Step 2: Enhance Commit Procedure with Validation

1. **Add Validation Checks After Each MCP Tool Call**:
   - Step 0 (Fix Errors): Validate `execute_pre_commit_checks()` response
   - Step 1 (Formatting): Validate `execute_pre_commit_checks()` response
   - Step 1.5 (Markdown Linting): Validate `fix_markdown_lint()` response
   - Step 2 (Type Checking): Validate `execute_pre_commit_checks()` response - **#2**
   - Step 3 (Code Quality): Validate `execute_pre_commit_checks()` response
   - Step 4 (Test Execution): Validate `execute_pre_commit_checks()` response - **#4**
   - Step 5 (Memory Bank): Validate `manage_file()` response
   - Step 6 (Roadmap Update): Validate `manage_file()` response - **#6**
   - Step 9 (Timestamp Validation): Validate `validate()` response
   - Step 10 (Roadmap Sync): Validate `validate()` response

2. **Add Protocol Enforcement**:
   - After each MCP tool call, check for failures
   - If failure detected, call `MCPToolFailureHandler.handle_failure()`
   - Stop commit procedure immediately
   - Block all subsequent steps

3. **Prevent Workarounds**:
   - Remove fallback method options when MCP tool fails
   - Block direct Python calls when MCP tool fails
   - Ensure protocol is followed automatically

### Step 3: Update Commit Procedure Documentation

1. **Enhance MCP Tool Failure Section**:
   - Add explicit validation requirements
   - Clarify that protocol is automatically enforced
   - Remove fallback method references
   - Add examples of proper failure handling

2. **Add Validation Checklist**:
   - After each MCP tool call, verify response is valid
   - Check for JSON parsing errors
   - Check for connection errors
   - Verify response structure matches expected format

3. **Update Step Descriptions**:
   - Add validation requirements to each step
   - Specify what constitutes a tool failure
   - Clarify that protocol violation blocks commit

### Step 4: Add Automated Investigation Plan Creation

1. **Create Investigation Plan Helper**:
   - Location: `src/cortex/core/investigation_plan_creator.py`
   - Use `create-plan.md` prompt structure
   - Automatically generate plan content
   - Include tool name, error details, step information

2. **Integrate with Roadmap**:
   - Automatically add investigation plans to roadmap
   - Add to "Blockers (ASAP Priority)" section
   - Link plan file properly
   - Update roadmap using `manage_file()` MCP tool

3. **User Notification**:
   - Generate summary with tool name, error, impact
   - Mark as FIX-ASAP priority
   - Provide plan location
   - Clear next steps

### Step 5: Add Tests and Validation

1. **Unit Tests**:
   - Test `MCPToolFailureHandler` failure detection
   - Test investigation plan creation
   - Test roadmap integration
   - Test user notification

2. **Integration Tests**:
   - Test commit procedure stops on MCP tool failure
   - Test protocol enforcement prevents workarounds
   - Test investigation plan is created automatically
   - Test roadmap is updated correctly

3. **Validation Tests**:
   - Test JSON parsing error detection
   - Test connection error detection
   - Test unexpected behavior detection
   - Test protocol violation prevention

## Success Criteria

- ✅ MCP tool failures are automatically detected
- ✅ Commit procedure stops immediately on tool failure
- ✅ Investigation plans are created automatically
- ✅ Plans are added to roadmap as blockers
- ✅ User is notified with clear summary
- ✅ Workarounds and fallbacks are prevented
- ✅ Protocol violations are caught and blocked
- ✅ All commit procedure steps have validation checks
- ✅ Comprehensive test coverage (90%+)
- ✅ Documentation updated with enforcement details

## Dependencies

- None (this is a blocker that must be fixed first)

## Risks & Mitigation

- **Risk**: Over-aggressive failure detection might block legitimate operations
  - **Mitigation**: Distinguish between tool failures and expected errors (validation failures)
  - **Mitigation**: Only detect actual tool failures (JSON parsing, connection, unexpected behavior)

- **Risk**: Investigation plan creation might fail if MCP tools are broken
  - **Mitigation**: Use standard file tools as fallback for plan creation only
  - **Mitigation**: Ensure plan creation doesn't depend on broken tools

- **Risk**: Protocol enforcement might be too strict
  - **Mitigation**: Focus on actual tool failures, not expected errors
  - **Mitigation**: Allow expected errors (validation failures) to proceed normally

## Technical Design

### MCPToolFailureHandler Class

```python
class MCPToolFailureHandler:
    """Handles MCP tool failures and enforces protocol."""
    
    def detect_failure(self, error: Exception, tool_name: str, step_name: str) -> bool:
        """Detect if error is an MCP tool failure."""
        # Check for JSON parsing errors
        # Check for connection errors
        # Check for unexpected behavior
        # Return True if tool failure detected
    
    def handle_failure(self, tool_name: str, error: Exception, step_name: str) -> None:
        """Handle MCP tool failure according to protocol."""
        # Stop commit procedure
        # Create investigation plan
        # Add to roadmap
        # Notify user
        # Raise exception to prevent continuation
    
    def create_investigation_plan(self, tool_name: str, error: Exception, step_name: str) -> str:
        """Create investigation plan for tool failure."""
        # Generate plan content
        # Save to plans directory
        # Return plan file path
    
    def add_to_roadmap(self, plan_path: str, tool_name: str) -> None:
        """Add investigation plan to roadmap as blocker."""
        # Read roadmap
        # Add plan entry
        # Update roadmap file
```

### Integration with Commit Procedure

```python
# After each MCP tool call:
try:
    result = await mcp_tool_call(...)
    # Validate response
    if not validate_response(result):
        raise MCPToolFailure("Invalid response structure")
except Exception as e:
    if MCPToolFailureHandler.detect_failure(e, tool_name, step_name):
        MCPToolFailureHandler.handle_failure(tool_name, e, step_name)
        # Protocol enforcement: stop commit procedure
        raise ProtocolViolation("MCP tool failure - commit procedure stopped")
    else:
        # Expected error (validation failure, etc.)
        # Handle normally
        pass
```

## Testing Strategy

1. **Unit Tests**:
   - Test failure detection for JSON parsing errors
   - Test failure detection for connection errors
   - Test investigation plan creation
   - Test roadmap integration
   - Test user notification

2. **Integration Tests**:
   - Test commit procedure stops on tool failure
   - Test protocol enforcement prevents workarounds
   - Test investigation plan is created automatically
   - Test roadmap is updated correctly

3. **End-to-End Tests**:
   - Test full commit procedure with tool failure
   - Verify protocol is followed automatically
   - Verify user is notified correctly
   - Verify investigation plan is created and linked

## Timeline

- **Step 1**: Create MCP Tool Failure Handler (2 hours)
- **Step 2**: Enhance Commit Procedure with Validation (3 hours)
- **Step 3**: Update Documentation (1 hour)
- **Step 4**: Add Automated Investigation Plan Creation (2 hours)
- **Step 5**: Add Tests and Validation (3 hours)
- **Total**: ~11 hours

## Notes

- This plan addresses the critical issue where agents can bypass the MCP tool failure protocol
- Focus on steps #2 (Type checking), #4 (Test execution), and #6 (Roadmap update) as requested
- Protocol enforcement must be automatic - agents should not be able to bypass it
- Investigation plans must be created automatically, not manually
- All MCP tool calls in commit procedure must have validation checks
