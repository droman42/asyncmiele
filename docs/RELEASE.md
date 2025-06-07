# Release Process

This document explains how to release a new version of AsyncMiele to PyPI.

## Prerequisites

1. **PyPI Trusted Publishing**: This project uses PyPI's trusted publishing feature, which eliminates the need for API tokens. The release workflow is configured to publish automatically when triggered by a version tag.

2. **GitHub Environment**: Ensure the `release` environment is configured in GitHub repository settings for additional security.

## Release Workflow

### 1. Update Version

Update the version in `pyproject.toml`:

```toml
[project]
name = "asyncmiele"
version = "0.3.0"  # Update this version
```

### 2. Update Changelog

Add release notes to `CHANGELOG.md`:

```markdown
## [0.3.0] - 2024-06-07

### Added
- New feature descriptions

### Changed
- Breaking changes or improvements

### Fixed
- Bug fixes
```

### 3. Commit Changes

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "Release v0.3.0"
git push origin main
```

### 4. Create Release Tag

Create a git tag that matches the version in `pyproject.toml`:

```bash
git tag v0.3.0
git push origin v0.3.0
```

**Important**: The tag version (without the 'v' prefix) must exactly match the version in `pyproject.toml`. If they don't match, the workflow will fail with a clear error message.

### 5. Automated Release Process

Once the tag is pushed, GitHub Actions will automatically:

1. **Validate Version**: Ensure git tag matches `pyproject.toml` version
2. **Build Distributions**: Create both wheel (.whl) and source distribution (.tar.gz)
3. **Test Installation**: Test the built packages on Python 3.11 and 3.12
4. **Publish to PyPI**: Upload to PyPI using trusted publishing
5. **Create GitHub Release**: Generate release notes from git commits
6. **Upload Artifacts**: Attach distribution files to GitHub release

## Build Configuration

### Package Contents

The build is configured to include only essential files:

**Included in wheel:**
- `asyncmiele/` - Main package code
- `resources/` - JSON data files and catalogs
- `asyncmiele/py.typed` - Type checking marker
- `LICENSE` - License file

**Included in source distribution:**
- All wheel contents
- `README.md`
- `CHANGELOG.md`
- `pyproject.toml`
- `MANIFEST.in`
- `examples/` - Example scripts and configurations

**Excluded from all distributions:**
- `tests/` - Test suite
- `docs/` - Documentation
- `.github/` - CI/CD configurations
- `.vscode/` - IDE settings
- Development configuration files
- Build artifacts and cache files

### Manual Build Testing

To test the build process locally:

```bash
# Install build dependencies
uv add --dev build check-manifest

# Validate MANIFEST.in
uv run check-manifest --verbose

# Build distributions
uv run python -m build --sdist --wheel --outdir dist/

# Test wheel installation
pip install dist/asyncmiele-*.whl
python -c "import asyncmiele; print('✅ Import successful')"
```

## Version Requirements

- **Python**: 3.11+
- **Version Format**: Semantic versioning (e.g., 1.2.3)
- **Pre-releases**: Supported with suffixes like `1.2.3rc1`, `1.2.3beta1`, `1.2.3alpha1`

## Troubleshooting

### Version Mismatch Error

If you see a version mismatch error:

```
❌ ERROR: Version mismatch!
   Git tag version: 1.2.4
   pyproject.toml version: 1.2.3
```

**Fix**: Either update `pyproject.toml` to match the tag, or create a new tag that matches `pyproject.toml`.

### Build Failures

Common build issues:

1. **MANIFEST.in errors**: Run `check-manifest --verbose` to see what files are missing or incorrectly included
2. **Package discovery issues**: Check the `[tool.setuptools.packages.find]` configuration in `pyproject.toml`
3. **Import errors**: Ensure all required dependencies are listed in `pyproject.toml`

### PyPI Publishing Issues

1. **Trusted publishing not configured**: Ensure the PyPI project has trusted publishing configured for this GitHub repository
2. **Environment protection**: Check that the `release` environment is properly configured in GitHub settings
3. **Permissions**: Verify the workflow has `id-token: write` permission for trusted publishing

## Manual Release (Emergency)

If automated release fails, you can publish manually:

```bash
# Build distributions
uv run python -m build

# Upload to PyPI (requires API token)
uv run twine upload dist/*
```

Note: Manual releases should be rare and only used in emergencies. The automated workflow is the preferred method. 