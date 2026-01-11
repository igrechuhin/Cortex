# Project Brief: MCP Memory Bank

## Overview

MCP Memory Bank is a comprehensive MCP (Model Context Protocol) server that implements a structured documentation system based on Cline's Memory Bank pattern. The system provides intelligent management of project knowledge, rules, plans, and context preservation for AI assistant environments.

## Core Requirements

- Hybrid storage with metadata tracking and version history
- Dynamic dependency graphs built from actual markdown links
- Content transclusion with `{{include: file.md#section}}` syntax
- Link validation with broken link detection
- Schema validation with required section enforcement
- Duplication detection with similarity scoring
- Quality metrics and health scoring (0-100)
- Token budget management with usage tracking
- Smart context optimization with relevance scoring
- Progressive loading strategies for efficient context delivery
- Content summarization for token reduction
- Custom rules integration with automatic indexing
- Usage pattern tracking and structure analysis
- AI-driven insights and refactoring suggestions
- Safe refactoring execution with rollback support
- Learning and adaptation from user feedback
- Shared rules repository with git submodule integration
- Standardized project structure management

## Goals

- Provide comprehensive Memory Bank management via MCP protocol
- Enable DRY (Don't Repeat Yourself) content through linking and transclusion
- Automate validation and quality checks
- Optimize token usage through smart loading and summarization
- Enable self-evolution through pattern analysis and refactoring
- Support cross-project rule sharing
- Achieve 9.5/10+ quality scores in all categories (Phase 7)
- Standardize project structure across all projects

## Project Scope

**In Scope:**

- Memory Bank file management (read, write, versioning, rollback)
- Link parsing and transclusion resolution
- Validation and quality metrics
- Token optimization and context loading
- Pattern analysis and refactoring suggestions
- Safe refactoring execution with approval workflow
- Shared rules management via git submodules
- Project structure standardization
- 52 MCP tools for comprehensive functionality
- Comprehensive test coverage (90%+ target)

**Out of Scope:**

- Direct file editing in external editors
- Real-time collaboration features
- Database storage (uses JSON for metadata)
- Web UI (MCP protocol only)
- Authentication/authorization (handled by MCP client)
