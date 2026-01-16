# Phase 27: Script Generation Prevention and Tooling Improvement

## Status

**Status**: PLANNING  
**Priority**: Medium  
**Created**: 2026-01-16  
**Target Completion**: 2026-01-30  
**Estimated Effort**: 30-40 hours

## Goal

Improve Cortex and Synapse tooling to prevent agents from needing to generate temporary scripts during sessions. Create mechanisms to detect, capture, and convert session-generated scripts into permanent MCP tools or Synapse scripts, reducing redundant script generation and improving agent efficiency.

## Context

### Current State

- **Existing Synapse Scripts**: 12 Python scripts in `.cortex/synapse/scripts/python/` for common tasks (linting, formatting, complexity analysis, etc.)
- **MCP Tools**: 53+ tools across 10 phases providing comprehensive functionality
- **Language-Agnostic Pattern**: System emphasizes using scripts from `.cortex/synapse/scripts/{language}/` instead of hardcoded commands
- **Agent Behavior**: Agents sometimes generate temporary scripts in session to accomplish tasks not covered by existing tooling

### Problem Statement

When agents encounter tasks that aren't directly supported by existing MCP tools or Synapse scripts, they generate temporary scripts during the session. This leads to:

- **Redundant Work**: Same scripts generated repeatedly across sessions
- **Lost Knowledge**: Session scripts are ephemeral and not preserved
- **Inconsistent Solutions**: Different agents may solve the same problem differently
- **Maintenance Burden**: No systematic way to identify and promote useful patterns
- **Tool Discovery Gap**: Agents may not be aware of existing tools/scripts that could solve their needs

### User Need

Create a systematic approach to:

1. **Detect** when agents generate scripts during sessions
2. **Capture** these scripts for analysis and potential promotion
3. **Analyze** script patterns to identify common needs
4. **Convert** useful session scripts into permanent tools/scripts
5. **Improve** tooling to cover common use cases proactively
6. **Document** existing tools/scripts to improve agent discovery

## Approach

### High-Level Strategy

1. **Script Detection System**: Monitor and capture agent-generated scripts during sessions
2. **Pattern Analysis**: Identify common patterns and use cases from captured scripts
3. **Tool Gap Analysis**: Compare captured scripts against existing MCP tools and Synapse scripts
4. **Promotion Pipeline**: Convert validated session scripts into permanent tools/scripts
5. **Tool Discovery Enhancement**: Improve documentation and discovery mechanisms
6. **Proactive Tooling**: Expand MCP tools and Synapse scripts to cover common patterns

### Architecture

```text
Script Generation Prevention System
├── Detection Layer
│   ├── Session Monitor - Tracks script creation during sessions
│   ├── Script Capture - Stores session scripts for analysis
│   └── Pattern Recognition - Identifies script types and purposes
├── Analysis Layer
│   ├── Script Analyzer - Analyzes captured scripts for patterns
│   ├── Gap Analyzer - Compares against existing tools/scripts
│   ├── Use Case Extractor - Identifies common use cases
│   └── Similarity Detector - Finds duplicate/redundant scripts
├── Promotion Layer
│   ├── Script Validator - Validates scripts for promotion
│   ├── Tool Converter - Converts scripts to MCP tools
│   ├── Script Integrator - Integrates into Synapse scripts
│   └── Documentation Generator - Creates tool/script documentation
├── Discovery Layer
│   ├── Tool Registry - Comprehensive tool/script registry
│   ├── Use Case Mapper - Maps use cases to tools/scripts
│   ├── Search Interface - Enhanced search for agents
│   └── Recommendation Engine - Suggests tools/scripts for tasks
└── Enhancement Layer
    ├── Tool Expander - Expands MCP tools to cover gaps
    ├── Script Library - Expands Synapse script library
    └── Pattern Library - Maintains reusable patterns
```

## Implementation Steps

### Step 1: Create Script Detection and Capture System

**Location**: `src/cortex/script_detection/`

**Files to Create**:

- `__init__.py` - Module initialization
- `session_monitor.py` - Monitors agent sessions for script generation
- `script_capture.py` - Captures and stores session scripts
- `pattern_recognizer.py` - Recognizes script types and purposes
- `storage.py` - Stores captured scripts with metadata

**Key Features**:

- Monitor file creation in session directories (e.g., `scripts/`, temporary locations)
- Detect script-like files (Python, shell, JavaScript, etc.)
- Capture script content, context, and metadata (timestamp, task description, agent)
- Classify scripts by type (utility, analysis, transformation, etc.)
- Store in `.cortex/script-capture/` directory with structured metadata

**Success Criteria**:

- Successfully captures 90%+ of session-generated scripts
- Metadata includes sufficient context for analysis
- Storage format supports efficient querying and analysis

### Step 2: Create Script Analysis System

**Location**: `src/cortex/script_analysis/`

**Files to Create**:

- `__init__.py` - Module initialization
- `script_analyzer.py` - Analyzes captured scripts for patterns
- `gap_analyzer.py` - Compares against existing tools/scripts
- `use_case_extractor.py` - Extracts common use cases
- `similarity_detector.py` - Detects duplicate/redundant scripts

**Key Features**:

- Analyze script content to identify purpose and functionality
- Extract use cases and requirements from scripts
- Compare against existing MCP tools and Synapse scripts
- Identify gaps where no existing tool/script covers the need
- Detect duplicate scripts solving the same problem
- Score scripts for promotion potential (reusability, quality, uniqueness)

**Success Criteria**:

- Accurately identifies script purposes and use cases
- Correctly identifies gaps in existing tooling
- Detects duplicate patterns with 80%+ accuracy
- Provides actionable insights for tooling improvements

### Step 3: Create Promotion Pipeline

**Location**: `src/cortex/script_promotion/`

**Files to Create**:

- `__init__.py` - Module initialization
- `script_validator.py` - Validates scripts for promotion
- `tool_converter.py` - Converts scripts to MCP tools
- `script_integrator.py` - Integrates into Synapse scripts
- `documentation_generator.py` - Generates tool/script documentation

**Key Features**:

- Validate scripts meet quality standards (error handling, documentation, tests)
- Convert validated scripts to MCP tools (async handlers, proper typing)
- Integrate scripts into Synapse script library (language-agnostic patterns)
- Generate comprehensive documentation for new tools/scripts
- Create migration guides for converting session scripts to permanent tools

**Success Criteria**:

- Successfully converts 70%+ of validated scripts to permanent tools/scripts
- Generated tools/scripts meet quality standards
- Documentation is comprehensive and accurate
- Migration process is clear and repeatable

### Step 4: Enhance Tool Discovery

**Location**: `src/cortex/discovery/`

**Files to Create**:

- `__init__.py` - Module initialization
- `tool_registry.py` - Comprehensive tool/script registry
- `use_case_mapper.py` - Maps use cases to tools/scripts
- `search_interface.py` - Enhanced search for agents
- `recommendation_engine.py` - Suggests tools/scripts for tasks

**Key Features**:

- Maintain comprehensive registry of all MCP tools and Synapse scripts
- Map use cases to appropriate tools/scripts
- Provide semantic search for agents to find relevant tools
- Recommend tools/scripts based on task description
- Provide examples and usage patterns for each tool/script

**Success Criteria**:

- Agents can discover relevant tools/scripts 90%+ of the time
- Search returns accurate results for common queries
- Recommendations are relevant and helpful
- Documentation is accessible and clear

### Step 5: Expand MCP Tools and Synapse Scripts

**Location**: Based on analysis results

**Key Activities**:

- Implement new MCP tools based on gap analysis
- Create new Synapse scripts for common patterns
- Enhance existing tools to cover additional use cases
- Create language-agnostic script templates
- Document all new tools/scripts comprehensively

**Success Criteria**:

- New tools/scripts cover 80%+ of identified gaps
- All new tools/scripts follow language-agnostic patterns
- Documentation is complete and accurate
- Tools/scripts are tested and validated

### Step 6: Create MCP Tool for Script Analysis

**Location**: `src/cortex/tools/script_analysis_tools.py`

**New MCP Tool**:

- `analyze_session_scripts` - Analyzes captured session scripts
- `suggest_tool_improvements` - Suggests tooling improvements based on analysis
- `promote_session_script` - Promotes a session script to permanent tool/script

**Key Features**:

- Allow agents to query captured scripts
- Get recommendations for tooling improvements
- Initiate promotion process for useful scripts
- View analysis results and insights

**Success Criteria**:

- Tool provides actionable insights
- Promotion process is straightforward
- Analysis results are accurate and useful

### Step 7: Integrate into Development Workflow

**Location**: `.cortex/synapse/prompts/`, `.github/workflows/`

**Key Activities**:

- Create prompt/command for agents to report script generation needs
- Add script analysis to CI/CD pipeline
- Create periodic review process for captured scripts
- Integrate tool discovery into agent workflow
- Add script promotion to development process

**Success Criteria**:

- Agents are aware of script capture and promotion process
- Script analysis runs automatically in CI/CD
- Periodic reviews identify and promote useful scripts
- Tool discovery is integrated into agent workflow

## Technical Design

### Script Capture Format

```json
{
  "script_id": "uuid",
  "timestamp": "2026-01-16T10:30:00Z",
  "agent_session": "session-id",
  "task_description": "Description of task that required script",
  "script_path": "relative/path/to/script",
  "script_content": "script content",
  "script_type": "python|shell|javascript|etc",
  "purpose": "utility|analysis|transformation|etc",
  "dependencies": ["dep1", "dep2"],
  "usage_context": "When and why this script was created",
  "promotion_status": "pending|analyzed|promoted|rejected",
  "similar_tools": ["tool1", "tool2"],
  "gap_analysis": {
    "existing_tools": [],
    "gap_reason": "No existing tool covers this use case"
  }
}
```

### Script Analysis Metrics

- **Reusability Score**: How likely is this script to be needed again?
- **Quality Score**: Code quality, error handling, documentation
- **Uniqueness Score**: How different is this from existing tools/scripts?
- **Promotion Potential**: Overall score for promotion

### Tool Conversion Process

1. **Validation**: Check script meets quality standards
2. **Analysis**: Determine if script should be MCP tool or Synapse script
3. **Conversion**: Transform script to appropriate format
4. **Testing**: Create tests for new tool/script
5. **Documentation**: Generate comprehensive documentation
6. **Integration**: Add to appropriate registry/library
7. **Migration**: Update any references to old script

## Testing Strategy

### Unit Tests

- Test script detection and capture
- Test script analysis algorithms
- Test gap analysis accuracy
- Test tool conversion process
- Test discovery and recommendation systems

### Integration Tests

- Test end-to-end script capture and promotion
- Test tool discovery in agent workflow
- Test CI/CD integration
- Test script analysis accuracy

### Manual Testing

- Verify script capture during agent sessions
- Test tool discovery with real agent queries
- Validate promotion process with sample scripts
- Test recommendation accuracy

## Success Criteria

### Functional Requirements

- ✅ Script detection captures 90%+ of session-generated scripts
- ✅ Script analysis accurately identifies patterns and gaps
- ✅ Promotion pipeline successfully converts 70%+ of validated scripts
- ✅ Tool discovery helps agents find relevant tools 90%+ of the time
- ✅ New tools/scripts cover 80%+ of identified gaps

### Quality Requirements

- ✅ All new code follows project standards (≤400 lines/file, ≤30 lines/function)
- ✅ Test coverage ≥90% for all new modules
- ✅ Type hints 100% coverage, no `Any` types
- ✅ Comprehensive documentation for all new tools/scripts
- ✅ Language-agnostic patterns followed for all scripts

### Performance Requirements

- ✅ Script analysis completes in <5 seconds for typical scripts
- ✅ Tool discovery returns results in <1 second
- ✅ Script capture adds <100ms overhead to file operations

## Risks & Mitigation

### Risk 1: Script Detection Overhead

**Risk**: Monitoring file operations adds significant overhead

**Mitigation**:

- Use efficient file watching mechanisms
- Filter by file extensions and locations
- Batch capture operations
- Make detection optional/configurable

### Risk 2: False Positives in Pattern Detection

**Risk**: Analysis incorrectly identifies patterns or gaps

**Mitigation**:

- Use multiple analysis algorithms
- Require human review for promotion
- Provide confidence scores
- Allow manual override

### Risk 3: Tool Bloat

**Risk**: Too many tools/scripts created, causing maintenance burden

**Mitigation**:

- Strict quality standards for promotion
- Regular review and cleanup of unused tools
- Consolidation of similar tools
- Clear deprecation process

### Risk 4: Agent Adoption

**Risk**: Agents don't use new tools/scripts, continue generating scripts

**Mitigation**:

- Improve tool discovery and documentation
- Provide clear examples and use cases
- Integrate discovery into agent workflow
- Monitor and improve based on usage

## Dependencies

- **Phase 21**: Health-Check and Optimization Analysis System (similar analysis patterns)
- **Existing MCP Tools**: Foundation for tool expansion
- **Synapse Scripts**: Existing script library to compare against

## Timeline

### Week 1: Detection and Capture (8-10 hours)

- Implement script detection system
- Create script capture mechanism
- Set up storage and metadata tracking
- Test with sample agent sessions

### Week 2: Analysis System (8-10 hours)

- Implement script analysis algorithms
- Create gap analysis system
- Build use case extraction
- Test analysis accuracy

### Week 3: Promotion Pipeline (6-8 hours)

- Create script validation system
- Implement tool conversion process
- Build script integration system
- Test promotion workflow

### Week 4: Discovery and Enhancement (8-12 hours)

- Enhance tool discovery system
- Expand MCP tools and Synapse scripts
- Create documentation and examples
- Integrate into development workflow

## Notes

- This phase complements Phase 21 (Health-Check System) by focusing specifically on script generation patterns
- The goal is proactive tooling improvement, not just reactive script capture
- Emphasis on language-agnostic patterns aligns with existing productContext requirements
- Tool discovery improvements benefit all agents, not just those generating scripts
- Consider integration with existing refactoring and pattern analysis tools
