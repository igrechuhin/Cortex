# TradeWing Integration Improvements - Suggestions for Cortex

**Date Created**: 26-02-23
**Source Project**: TradeWing (Swift/macOS trading bot)
**Status**: Suggestions for consideration

## Overview

During planning for Cortex integration with TradeWing (a Swift/macOS trading bot project), several capability gaps were identified. These suggestions would improve Cortex's ability to support Swift-based projects and ML-heavy workflows.

## Suggestion 1: Add Swift Language Adapter to Synapse

**Current State**: Synapse supports Python, TypeScript, Go, Rust, and Java language adapters but has no Swift support.

**Proposed Enhancement**: Add a Swift language adapter that understands:

- SwiftPM package structure (`Package.swift`, `Sources/`, `Tests/`)
- Swift access control (`public`, `internal`, `private`, `fileprivate`)
- Swift-specific patterns (actors, `@Sendable`, structured concurrency)
- One-type-per-file convention enforcement
- File length and function length limits
- Swift naming conventions (camelCase properties, PascalCase types)
- DocC documentation format validation

**Impact**: Enables Synapse to enforce Swift coding standards automatically, which TradeWing and other Swift projects require.

## Suggestion 2: Add SwiftFormat Integration to Commit Pipeline

**Current State**: Commit pipeline supports Black (Python), Prettier (JS/TS), and gofmt (Go) but has no Swift formatter integration.

**Proposed Enhancement**: Add SwiftFormat as a configurable formatter in the commit pipeline:

- Auto-detect `swiftformat` binary availability
- Support `.swiftformat` configuration files
- Run `swiftformat --lint .` as a pre-commit check
- Run `swiftformat .` as an auto-fix step
- Report formatting violations in the standard Cortex format

**Impact**: Eliminates formatting inconsistencies in Swift projects as part of the standard commit workflow.

## Suggestion 3: Add SwiftPM Build Validation to Preflight Checks

**Current State**: Preflight checks support npm, cargo, go build, and pip but not SwiftPM.

**Proposed Enhancement**: Add SwiftPM build validation:

- Detect `Package.swift` in project root
- Run `swift build` as a preflight check
- Parse Swift compiler warnings and errors
- Treat compiler warnings as errors (configurable)
- Support custom build scripts (e.g., `build.sh`)

**Impact**: Catches build failures before commit, matching the behavior already available for other ecosystems.

## Suggestion 4: Consider MLOps-Specific Tools

**Current State**: Cortex focuses on general software development workflows. No specific support for ML experiment tracking, model registry, or training pipeline management.

**Proposed Enhancement**: Add optional MLOps tools for ML-heavy projects:

- **Experiment Registry**: Track training runs with hyperparameters and metrics
- **Model Registry**: Version and promote model artifacts
- **Data Versioning**: Hash-based tracking of training data snapshots
- **Training Dashboard**: Summary of recent training runs and model performance
- **Model Comparison**: Side-by-side comparison of experiment runs

These could be implemented as an optional Cortex plugin/extension rather than core functionality.

**Impact**: Projects like TradeWing that combine software engineering with ML workflows would benefit from integrated experiment tracking rather than building custom infrastructure.

## Suggestion 5: Xcode/SwiftPM Project Structure Detection

**Current State**: Project initialization detects npm, cargo, go.mod, and pip-based projects but not SwiftPM or Xcode projects.

**Proposed Enhancement**: Add detection for Swift project structures:

- Detect `Package.swift` for SwiftPM projects
- Detect `.xcodeproj` / `.xcworkspace` for Xcode projects
- Auto-configure build command (`swift build` or `xcodebuild`)
- Auto-configure test command (`swift test` or `xcodebuild test`)
- Detect test targets and coverage configuration
- Recognize common Swift project layouts (`Sources/`, `Tests/`)

**Impact**: Swift developers get automatic project configuration on Cortex initialization, matching the experience for other ecosystems.

## Suggestion 6: Memory Bank Migration Tool

**Current State**: Projects using the legacy IDE Memory Bank layout need manual migration to `.cortex/memory-bank/` format.

**Proposed Enhancement**: Add a migration tool that:

- Detects existing legacy IDE Memory Bank directories
- Converts files to Cortex-compatible format (adds frontmatter metadata)
- Optionally maintains backward-compatible symlinks
- Configures bi-directional sync between `.cursor/` and `.cortex/` memory banks
- Preserves all existing content and timestamps
- Provides a dry-run mode to preview changes

**Impact**: Reduces friction for projects migrating from Cursor-based workflows to Cortex, which is the exact situation TradeWing faces.

## Priority Ranking

1. **Swift Language Adapter** (High) - Blocks Synapse usage for Swift projects
2. **SwiftFormat Integration** (High) - Blocks commit pipeline usage for Swift projects
3. **Memory Bank Migration Tool** (Medium) - One-time need but reduces migration friction
4. **SwiftPM Build Validation** (Medium) - Important for CI-like preflight checks
5. **Project Structure Detection** (Medium) - Quality of life for initial setup
6. **MLOps Tools** (Low) - Niche but valuable for ML-heavy projects

## TradeWing Context

TradeWing is a production-grade trading bot built in Swift 6.1 for macOS. It features:

- 100+ technical indicators computed across 7 time intervals
- MLX-based LSTM training with hyperparameter search
- Ensemble model prediction with quality gates
- GRDB/SQLite storage with connection pooling
- gRPC integration with T-Invest broker API
- Telegram signal delivery with under-30s end-to-end latency
- 6292+ tests across 35 targets

The project would be an excellent test case for Swift-specific Cortex features.
