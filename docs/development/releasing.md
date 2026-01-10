# Release Process Guide

This guide provides a comprehensive overview of the release process for Cortex, including version management, testing, packaging, publishing, and post-release verification.

## Table of Contents

1. [Release Overview](#release-overview)
2. [Pre-Release Checklist](#pre-release-checklist)
3. [Version Bumping](#version-bumping)
4. [Changelog](#changelog)
5. [Git Tagging](#git-tagging)
6. [Building the Package](#building-the-package)
7. [Publishing to PyPI](#publishing-to-pypi)
8. [GitHub Releases](#github-releases)
9. [Post-Release Verification](#post-release-verification)
10. [Hotfix Releases](#hotfix-releases)
11. [Rollback Process](#rollback-process) <!-- markdownlint-disable-line MD051 -->
12. [Release Automation](#release-automation)
13. [Common Issues](#common-issues)
14. [Release Checklist](#release-checklist)

## Release Overview

### Release Types

Cortex follows **Semantic Versioning** (semver): `MAJOR.MINOR.PATCH`

#### Major Release (MAJOR.0.0)

- **When**: Breaking changes to API or public interfaces
- **Example**: `0.1.0` → `1.0.0`
- **Impact**: Users must update code to be compatible
- **Frequency**: Rarely, only for significant architectural changes

#### Minor Release (X.MINOR.0)

- **When**: New features added with backward compatibility maintained
- **Example**: `0.1.0` → `0.2.0`
- **Impact**: Users can upgrade safely; new features available
- **Frequency**: Every 2-4 weeks for active development

#### Patch Release (X.Y.PATCH)

- **When**: Bug fixes, performance improvements, or documentation updates
- **Example**: `0.1.0` → `0.1.1`
- **Impact**: Users should upgrade to get fixes
- **Frequency**: As needed (1-5 days)

#### Pre-Release Versions

- **Alpha**: `0.1.0a1` (early development)
- **Beta**: `0.1.0b1` (approaching stability)
- **Release Candidate**: `0.1.0rc1` (final testing before release)

### Semantic Versioning Rules

```text
MAJOR.MINOR.PATCH[+prerelease]
│      │     │     └─ Pre-release suffix (optional)
│      │     └─ Patch: Bug fixes, patches
│      └─ Minor: New features, backward compatible
└─ Major: Breaking changes, new major features
```

**Rules**:

1. Increment MAJOR when API breaks backward compatibility
2. Increment MINOR when adding features in backward-compatible manner
3. Increment PATCH when fixing bugs
4. Reset lower version numbers when incrementing higher ones:
   - `1.2.3` → `2.0.0` (not `2.1.0`)
   - `1.2.3` → `1.3.0` (not `1.3.1`)

## Pre-Release Checklist

Before creating a release, complete the following checklist:

### 1. Code Quality Checks

- [ ] All code formatted with Black

  ```bash
  black .
  isort .
  ```

- [ ] No type hint violations

  ```bash
  # Run Pyright type checking
  pyright src/
  ```

- [ ] No production file exceeds 400 lines
- [ ] No function exceeds 30 logical lines
- [ ] No bare `except:` clauses
- [ ] All Python 3.13+ features used correctly

### 2. Testing Requirements

- [ ] All unit tests pass

  ```bash
  pytest tests/unit/ -v
  ```

- [ ] All integration tests pass

  ```bash
  pytest tests/integration/ -v
  ```

- [ ] Overall test coverage ≥ 90%

  ```bash
  pytest --cov=src --cov-report=term-missing --cov-fail-under=90
  ```

- [ ] No skipped tests without justification
- [ ] All tests follow AAA (Arrange-Act-Assert) pattern

### 3. Documentation Updates

- [ ] README.md updated with new features
- [ ] CHANGELOG.md updated with version and changes
- [ ] API documentation updated in `docs/api/`
- [ ] Getting started guide reflects new features
- [ ] Contributing guide is current
- [ ] Memory bank `.cursor/memory-bank/` files updated

### 4. Dependency Verification

- [ ] Run `uv lock` to update lock file

  ```bash
  uv lock
  ```

- [ ] No deprecated dependencies
- [ ] No security vulnerabilities in dependencies

  ```bash
  # Check for known vulnerabilities
  pip install safety
  safety check
  ```

- [ ] Dependencies in `pyproject.toml` are accurate

### 5. Code Review

- [ ] All changes reviewed by at least one maintainer
- [ ] No merge conflicts
- [ ] Branch is up-to-date with main

### 6. Git Status Clean

- [ ] All changes committed

  ```bash
  git status  # Should be clean
  ```

- [ ] No untracked files (except `.env`, `.venv/`, etc.)
- [ ] Branch is clean and ready for tagging

## Version Bumping

### Updating Version in pyproject.toml

The version is defined in `pyproject.toml` at the top level:

```toml
[project]
name = "cortex"
version = "0.2.0"  # ← Update this
description = "Memory Bank helper for AI assistant with hybrid storage and intelligent metadata tracking"
```

### Steps to Bump Version

1. **Determine the new version** based on changes:
   - Breaking changes → MAJOR bump
   - New features → MINOR bump
   - Bug fixes only → PATCH bump

2. **Update `pyproject.toml`**:

   ```toml
   [project]
   version = "0.3.0"  # Example: 0.2.0 → 0.3.0
   ```

3. **Commit the version bump**:

   ```bash
   git add pyproject.toml
   git commit -m "bump: version 0.2.0 → 0.3.0"
   ```

### Version Bump Examples

```bash
# Patch release (bug fixes)
# Old: 0.2.0 → New: 0.2.1
sed -i '' 's/version = "0.2.0"/version = "0.2.1"/' pyproject.toml

# Minor release (new features)
# Old: 0.2.1 → New: 0.3.0
sed -i '' 's/version = "0.2.1"/version = "0.3.0"/' pyproject.toml

# Major release (breaking changes)
# Old: 0.3.0 → New: 1.0.0
sed -i '' 's/version = "0.3.0"/version = "1.0.0"/' pyproject.toml
```

## Changelog

### Format and Structure

Maintain a `CHANGELOG.md` file in the root directory documenting all changes:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New feature description

### Changed
- Changed feature description

### Fixed
- Bug fix description

### Removed
- Removed feature description

## [0.3.0] - 2024-12-25

### Added
- New refactoring analysis tools
- Support for pattern-based refactoring suggestions
- Progressive loading optimization

### Changed
- Improved token counter performance
- Updated transclusion engine for faster resolution

### Fixed
- Fixed race condition in file watcher
- Corrected schema validation edge cases

## [0.2.0] - 2024-12-20

### Added
- Initial release with core functionality
```

### Categories for Changes

Use these standard categories:

- **Added**: New features
- **Changed**: Changes to existing features
- **Deprecated**: Features being phased out
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security vulnerability fixes

### Keeping Changelog Updated

1. **During development**: Add entries to `[Unreleased]` section
2. **Before release**: Move `[Unreleased]` to new version section
3. **Entry format**:

   ```markdown
   - Brief description of change
   - Another change description
   ```

### Release Notes Format

When creating release notes, use this template:

```markdown
## Cortex v0.3.0

### Highlights

- New pattern-based refactoring system
- 30% performance improvement in token counting
- Enhanced validation with custom rule support

### New Features

- `get_refactoring_suggestions` tool for automated code improvement
- Custom validation rules via `configure_validation` tool
- Progressive loading strategy for large memory banks

### Bug Fixes

- Fixed memory leak in file watcher (Issue #42)
- Corrected edge cases in schema validation
- Improved error messages for missing dependencies

### Performance

- Token counting now 30% faster with optimized caching
- Reduced memory footprint for large projects by 15%

### Breaking Changes

- Removed deprecated `analyze_memory_bank` tool (use `analyze_structure` instead)
- Changed return type of `get_optimization_config` (see migration guide)

### Dependencies

- Updated watchdog to 4.0.2
- Updated tiktoken to 0.6.0

### Contributors

- @username1 for feature X
- @username2 for bug fix Y
```

## Git Tagging

### Tag Naming Convention

Tags follow semantic versioning with a `v` prefix:

```text
v0.3.0          # Release version
v0.3.0-alpha.1  # Alpha pre-release
v0.3.0-beta.1   # Beta pre-release
v0.3.0-rc.1     # Release candidate
```

### Creating Git Tags

1. **Create annotated tag** (recommended):

   ```bash
   git tag -a v0.3.0 -m "Release version 0.3.0

   New Features:
   - Pattern-based refactoring
   - Progressive loading optimization

   Bug Fixes:
   - Fixed file watcher race condition
   - Corrected schema validation edge cases

   Breaking Changes:
   - Removed deprecated analyze_memory_bank tool"
   ```

2. **Verify tag was created**:

   ```bash
   git tag -l v0.3.0  # List tag
   git show v0.3.0    # Show tag details
   ```

3. **Push tags to remote**:

   ```bash
   git push origin v0.3.0
   # Or push all tags
   git push origin --tags
   ```

### Tag Verification

```bash
# List all tags
git tag -l

# Show tag details
git show v0.3.0

# Verify tag is signed (if using GPG)
git verify-tag v0.3.0
```

### Deleting Tags (If Needed)

```bash
# Delete local tag
git tag -d v0.3.0

# Delete remote tag
git push origin --delete v0.3.0

# Or use older syntax
git push origin :refs/tags/v0.3.0
```

## Building the Package

### Build Prerequisites

- `uv` installed (see [CLAUDE.md](../../CLAUDE.md#building--distribution))
- Python 3.10+ available
- All dependencies in `pyproject.toml` correct

### Build Verification

Before building, verify the build system is configured:

```toml
# pyproject.toml
[build-system]
requires = ["uv_build"]
build-backend = "uv_build"
```

### Building Locally

```bash
# Install build tools
uv pip install build

# Build both wheel and source distributions
python -m build

# Or using uv_build directly
uv build
```

### Build Artifacts

Building creates a `dist/` directory with:

```text
dist/
├── cortex-0.3.0-py3-none-any.whl  # Wheel (binary package)
└── cortex-0.3.0.tar.gz             # Source distribution
```

### Verifying Build Artifacts

1. **Check file existence**:

   ```bash
   ls -lh dist/
   ```

2. **Verify wheel contents**:

   ```bash
   unzip -l dist/cortex-0.3.0-py3-none-any.whl
   ```

3. **Test installation from wheel**:

   ```bash
   python -m venv test_env
   source test_env/bin/activate
   pip install dist/cortex-0.3.0-py3-none-any.whl
   python -c "import cortex; print(cortex.__version__)"
   deactivate
   rm -rf test_env
   ```

### Cleaning Build Artifacts

```bash
# Remove build artifacts
rm -rf dist/ build/ *.egg-info/

# Or use build cleanup
python -m build --clean
```

## Publishing to PyPI

### Publishing Prerequisites

1. **PyPI Account**: Create account at <https://pypi.org>
2. **API Token**: Generate at <https://pypi.org/manage/account/token/>
3. **Configure credentials**:

   ```bash
   # Create ~/.pypirc
   [distutils]
   index-servers =
       pypi
       testpypi

   [pypi]
   repository = https://upload.pypi.org/legacy/
   username = __token__
   password = pypi-AgEIcHlwaS5vcmc...  # Your token

   [testpypi]
   repository = https://test.pypi.org/legacy/
   username = __token__
   password = pypi-AgEIcHlwaS5vcmc...  # Your test token
   ```

### Test PyPI Publishing (Recommended First)

1. **Publish to Test PyPI**:

   ```bash
   python -m twine upload --repository testpypi dist/*
   ```

2. **Verify test publication**:

   ```bash
   # Visit https://test.pypi.org/project/cortex/
   # Check that v0.3.0 appears
   ```

3. **Test installation from Test PyPI**:

   ```bash
   python -m venv test_env
   source test_env/bin/activate
   pip install --index-url https://test.pypi.org/simple/ cortex==0.3.0
   python -c "import cortex; print('Success!')"
   deactivate
   rm -rf test_env
   ```

### Production PyPI Publishing

1. **Build release artifacts**:

   ```bash
   rm -rf dist/ build/
   python -m build
   ```

2. **Publish to PyPI**:

   ```bash
   python -m twine upload dist/*
   ```

3. **Enter credentials** when prompted (use token)

4. **Verify publication**:

   ```bash
   # Visit https://pypi.org/project/cortex/
   # Check that v0.3.0 appears and is installable
   ```

5. **Test production installation**:

   ```bash
   python -m venv test_env
   source test_env/bin/activate
   pip install cortex==0.3.0
   python -c "import cortex; print('Success!')"
   deactivate
   rm -rf test_env
   ```

### Publishing with Twine

```bash
# Install twine
pip install twine

# Check release before uploading
twine check dist/*

# Upload to PyPI
twine upload dist/*

# Verbose upload with progress
twine upload -r pypi --verbose dist/*
```

### Troubleshooting Publishing

| Issue | Solution |
|-------|----------|
| "Invalid distribution" | Run `twine check dist/*` to verify artifacts |
| "Authentication failed" | Verify token in `~/.pypirc` is correct |
| "Already exists" | Version already published; increment version |
| "Forbidden" | Check project permissions on PyPI.org |

## GitHub Releases

### Creating GitHub Releases

1. **Push tag to remote**:

   ```bash
   git push origin v0.3.0
   ```

2. **Create release on GitHub**:

   ```bash
   gh release create v0.3.0 \
     --title "Cortex v0.3.0" \
     --notes-file CHANGELOG.md
   ```

3. **Or via GitHub Web Interface**:
   - Go to [Releases](https://github.com/igrechuhin/cortex/releases)
   - Click "Draft a new release"
   - Select tag `v0.3.0`
   - Fill in title and description
   - Click "Publish release"

### Release Notes Template

```text
# Cortex v0.3.0

## Highlights

- Pattern-based refactoring system
- 30% performance improvement
- Enhanced validation support

## What's Changed

### Features
- New `get_refactoring_suggestions` tool
- Custom validation rules support
- Progressive loading strategy

### Bug Fixes
- Fixed file watcher race condition (#42)
- Corrected schema validation edge cases
- Improved error messages

### Performance
- Token counting 30% faster
- Reduced memory footprint by 15%

### Breaking Changes
- Removed deprecated `analyze_memory_bank` tool
- Changed `get_optimization_config` return type

## Installation

\`\`\`bash
pip install --upgrade cortex==0.3.0
\`\`\`

Or with uvx:

\`\`\`bash
uvx --from git+https://github.com/igrechuhin/cortex.git@v0.3.0 cortex
\`\`\`

## Contributors

- @username1 for feature X
- @username2 for bug fix Y

**Full Changelog**: <https://github.com/igrechuhin/cortex/compare/v0.2.0...v0.3.0>
```

### Attaching Artifacts

1. **Download release artifacts** from local `dist/`:

   ```bash
   gh release upload v0.3.0 dist/*
   ```

1. **Or manually**:
   - Go to GitHub release page
   - Click "Edit"
   - Drag and drop `dist/cortex-0.3.0-py3-none-any.whl` and `.tar.gz`
   - Save

## Post-Release Verification

### 1. Verify PyPI Publication

```bash
# Check PyPI page
curl -s https://pypi.org/project/cortex/json | \
  jq '.releases | keys[-1]'  # Last released version

# Install and test
pip install cortex==0.3.0
python -c "import cortex; print('✓ Installation successful')"
```

### 2. Verify GitHub Release

- [ ] Release visible at <https://github.com/igrechuhin/cortex/releases>
- [ ] All artifacts attached (wheel and source distribution)
- [ ] Release notes are complete and accurate
- [ ] Tag is correctly associated with release

### 3. Update Documentation

- [ ] Update docs/index.md with new version
- [ ] Update getting-started.md if installation changed
- [ ] Update api/modules.md if API changed
- [ ] Add migration guide if breaking changes

### 4. Announce Release

Post announcement to:

- [ ] GitHub Discussions
- [ ] Project communication channels
- [ ] Relevant community forums
- [ ] Social media (if applicable)

Example announcement:

```text
🎉 Cortex v0.3.0 is now available!

New Features:
- Pattern-based refactoring
- Progressive loading optimization
- Enhanced validation

Install: pip install --upgrade cortex

See release notes: https://github.com/igrechuhin/cortex/releases/tag/v0.3.0
```

### 5. Monitor for Issues

- [ ] Watch for bug reports in first 24 hours
- [ ] Be ready with quick patch release if critical bug found
- [ ] Respond to user questions about new features

## Hotfix Releases

### When to Use Hotfix

Use hotfix releases (patch version bump) for:

- Critical security vulnerabilities
- Severe bugs preventing normal usage
- Data corruption issues
- Breaking the main workflow

### Hotfix Process

1. **Create hotfix branch** from latest release tag:

   ```bash
   git checkout v0.2.0  # Current release
   git checkout -b hotfix/critical-bug
   ```

2. **Fix the bug**:
   - Make necessary code changes
   - Test thoroughly
   - Update CHANGELOG.md

3. **Bump patch version**:

   ```bash
   # 0.2.0 → 0.2.1
   sed -i '' 's/version = "0.2.0"/version = "0.2.1"/' pyproject.toml
   ```

4. **Commit and tag**:

   ```bash
   git add -A
   git commit -m "fix: critical bug in file watcher

   - Fixed race condition causing data loss
   - Added regression test
   - Version 0.2.0 → 0.2.1"

   git tag -a v0.2.1 -m "Hotfix release v0.2.1 - Critical bug fix"
   ```

5. **Push and publish**:

   ```bash
   git push origin hotfix/critical-bug
   git push origin v0.2.1

   # Build and publish to PyPI
   python -m build
   python -m twine upload dist/*
   ```

6. **Merge back to main**:

   ```bash
   git checkout main
   git pull origin main
   git merge --no-ff hotfix/critical-bug
   git push origin main
   ```

### Hotfix Release Notes

```text
# Cortex v0.2.1 (Hotfix)

## Critical Fix

**Fix**: Race condition in file watcher causing data loss
- Fixes: #48
- Impact: All users on 0.2.0 should upgrade immediately

## Installation

\`\`\`bash
pip install --upgrade cortex==0.2.1
\`\`\`

## Details

The file watcher had a race condition when multiple changes occurred simultaneously.
This could result in file data being lost during concurrent write operations.

This release includes:

- Fixed synchronization in file watcher
- Additional locking mechanism
- New regression test to prevent recurrence

## Contributors

- @maintainer1 for identifying and fixing the issue
```

## Rollback Process

### When to Rollback

Rollback a release if:

- Critical bug discovered immediately after release
- Security vulnerability exposed
- Data corruption reported
- Severe performance regression
- Breaking issue in most common workflows

### Rollback Steps

1. **Yank version from PyPI** (mark as unavailable):

   ```bash
   # Using pip-audit or twine
   pip install twine keyring

   # Don't use twine to yank; use PyPI website instead
   # Go to https://pypi.org/project/cortex/
   # Click version number, click "Yank this release"
   ```

2. **Publish rollback announcement**:

   ```text
   ⚠️ SECURITY/BUG ALERT: v0.3.0 has been yanked

   **Issue**: Critical bug in memory bank validation

   **Status**: Yanked from PyPI and GitHub Releases

   **Action Required**:
   - If you installed v0.3.0, please downgrade to v0.2.1
   - Version v0.3.1 with fix coming within 24 hours

   \`\`\`bash
   pip install cortex==0.2.1
   \`\`\`

   **Apologies** for the inconvenience
   ```

3. **Create and publish fix**:

   ```bash
   # Create patch release with fix
   git checkout v0.3.0  # Problematic version
   git checkout -b hotfix/v0.3.1

   # Fix the issue
   # ... changes ...

   # Bump to 0.3.1
   sed -i '' 's/version = "0.3.0"/version = "0.3.1"/' pyproject.toml

   git commit -m "fix: critical bug from v0.3.0

   - Fixed memory bank validation edge case
   - Version 0.3.0 → 0.3.1"

   git tag -a v0.3.1 -m "Hotfix release v0.3.1"
   git push origin v0.3.1

   # Publish new version
   python -m build
   python -m twine upload dist/*
   ```

4. **Update documentation**:
   - Update security advisories
   - Document what was wrong and how it's fixed
   - Add to CHANGELOG.md

5. **Post-rollback announcement**:

   ```markdown
   ✅ RESOLVED: v0.3.1 now available with fix

   v0.3.0 had a critical bug that has been fixed in v0.3.1.

   **Install the fixed version**:
   `pip install --upgrade cortex==0.3.1`
   ```

### Preventing Rollback Situations

- [ ] Run comprehensive tests before release
- [ ] Have beta releases for major changes
- [ ] Get community testing before production
- [ ] Monitor immediately after release
- [ ] Have quick response plan for hotfixes

## Release Automation

### CI/CD Integration

While Cortex doesn't currently have automated release CI/CD, here's a recommended setup:

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install build twine

      - name: Build distribution
        run: python -m build

      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*

      - name: Create GitHub Release
        uses: actions/create-release@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          tag_name: ${{ github.ref }}
          release_name: Release ${{ github.ref }}
          draft: false
          prerelease: false
```

### Manual Release Checklist Automation

```bash
#!/bin/bash
# scripts/pre-release-check.sh

set -e

echo "🔍 Running pre-release checks..."

# Code quality
echo "✓ Code formatting..."
black . --check
isort . --check

# Testing
echo "✓ Running tests..."
pytest tests/ -v --cov=src --cov-fail-under=90

# Type checking
echo "✓ Type checking..."
pyright src/

# Git status
echo "✓ Checking git status..."
if [ -z "$(git status --porcelain)" ]; then
    echo "  ✓ Working directory clean"
else
    echo "  ✗ Uncommitted changes found"
    exit 1
fi

echo "✅ All pre-release checks passed!"
```

## Common Issues

### Issue: "Version already exists on PyPI"

**Cause**: Version was already published

**Solution**:

1. Create new version number (increment patch/minor/major)
2. Update `pyproject.toml`
3. Rebuild and republish

```bash
# Change version
sed -i '' 's/version = "0.3.0"/version = "0.3.1"/' pyproject.toml

# Rebuild
rm -rf dist/ build/
python -m build

# Republish
python -m twine upload dist/*
```

### Issue: "Invalid distribution format"

**Cause**: Build artifacts are corrupted or incomplete

**Solution**:

```bash
# Verify artifacts
python -m twine check dist/*

# Rebuild
rm -rf dist/ build/ *.egg-info
python -m build

# Check again
python -m twine check dist/*
```

### Issue: "Authentication failed on PyPI"

**Cause**: Invalid credentials or token

**Solution**:

1. Generate new API token on PyPI.org
2. Update `~/.pypirc`:

   ```ini
   [pypi]
   repository = https://upload.pypi.org/legacy/
   username = __token__
   password = pypi-AgEIcHlwaS...  # New token
   ```

3. Republish

### Issue: "Tag already exists"

**Cause**: Tag was previously created

**Solution**:

```bash
# Delete old tag (if wrong)
git tag -d v0.3.0
git push origin --delete v0.3.0

# Create new tag with updated version
git tag -a v0.3.1 -m "Release v0.3.1"
git push origin v0.3.1
```

### Issue: "Can't install from PyPI"

**Cause**: Package not properly published or wrong version

**Solution**:

```bash
# Check PyPI page
pip index versions cortex

# Wait a few minutes for PyPI cache to update
sleep 300

# Try again
pip install --upgrade cortex

# Or specify version
pip install cortex==0.3.0
```

### Issue: "Tests fail after version bump"

**Cause**: Version string hardcoded in tests

**Solution**:

```bash
# Find hardcoded version strings
grep -r "0.2.0" tests/

# Update in test files
sed -i '' 's/0.2.0/0.3.0/g' tests/test_version.py

# Rerun tests
pytest tests/ -v
```

## Release Checklist

Use this comprehensive checklist for every release:

### Phase 1: Preparation (24 hours before)

- [ ] Create release branch: `git checkout -b release/v0.3.0`
- [ ] Review all changes since last release
- [ ] Update CHANGELOG.md with all changes
- [ ] Update version in `pyproject.toml`
- [ ] Run `uv lock` to update lock file
- [ ] Verify all tests pass locally

### Phase 2: Code Quality

- [ ] Format code: `black . && isort .`
- [ ] Run type checking: `pyright src/`
- [ ] Run full test suite: `pytest tests/ -v`
- [ ] Check coverage: `pytest --cov=src --cov-fail-under=90`
- [ ] Verify no files exceed 400 lines
- [ ] Verify no functions exceed 30 lines
- [ ] Verify no bare `except:` statements

### Phase 3: Documentation

- [ ] Update README.md with new features
- [ ] Update docs/index.md
- [ ] Update docs/getting-started.md if needed
- [ ] Update docs/architecture.md if structure changed
- [ ] Update docs/api/modules.md if API changed
- [ ] Add migration guide if breaking changes
- [ ] Update CLAUDE.md if development changes

### Phase 4: Git & Tags

- [ ] Commit version bump: `git commit -m "bump: version 0.2.0 → 0.3.0"`
- [ ] Create annotated tag: `git tag -a v0.3.0 -m "Release v0.3.0"`
- [ ] Verify tag: `git show v0.3.0`
- [ ] Push changes: `git push origin release/v0.3.0`
- [ ] Push tag: `git push origin v0.3.0`

### Phase 5: Building

- [ ] Clean old artifacts: `rm -rf dist/ build/`
- [ ] Build package: `python -m build`
- [ ] Verify artifacts: `ls -lh dist/`
- [ ] Check wheel: `python -m twine check dist/*`
- [ ] Test installation:

  ```bash
  python -m venv test_env
  source test_env/bin/activate
  pip install dist/cortex-0.3.0-py3-none-any.whl
  python -c "import cortex; print('✓')"
  deactivate
  ```

### Phase 6: Publishing

- [ ] Publish to Test PyPI: `twine upload -r testpypi dist/*`
- [ ] Verify on Test PyPI: Visit <https://test.pypi.org/project/cortex/>
- [ ] Test from Test PyPI:

  ```bash
  pip install --index-url https://test.pypi.org/simple/ cortex==0.3.0
  ```

- [ ] Publish to PyPI: `twine upload dist/*`
- [ ] Verify on PyPI: Visit <https://pypi.org/project/cortex/>

### Phase 7: GitHub Release

- [ ] Create GitHub release: `gh release create v0.3.0`
- [ ] Add release notes from CHANGELOG.md
- [ ] Attach artifacts: `gh release upload v0.3.0 dist/*`
- [ ] Verify release visible: <https://github.com/igrechuhin/cortex/releases>

### Phase 8: Post-Release

- [ ] Update docs/index.md with new version
- [ ] Announce release on GitHub Discussions
- [ ] Monitor for issues (first 24 hours)
- [ ] Test installation in clean environment
- [ ] Verify uvx deployment works:

  ```bash
  uvx --from git+https://github.com/igrechuhin/cortex.git@v0.3.0 cortex
  ```

- [ ] Update memory bank files
- [ ] Create issue for next release planning

### Phase 9: Cleanup

- [ ] Delete release branch: `git branch -d release/v0.3.0`
- [ ] Start new development cycle
- [ ] Plan next release features

---

## See Also

- [Contributing Guide](./contributing.md) - Development guidelines
- [Testing Guide](./testing.md) - Test requirements and best practices
- [CLAUDE.md](../../CLAUDE.md) - Project architecture and setup
- [README.md](../../README.md) - Installation and usage
- [Semantic Versioning](https://semver.org/) - Official semver specification
- [Keep a Changelog](https://keepachangelog.com/) - Changelog format
