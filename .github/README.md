# GitHub Actions CI/CD

This directory contains the GitHub Actions workflows for the AsyncMiele project.

## Workflows

### Test Suite (`test.yml`)

This workflow runs automatically on:
- All pushes to `main`, `master`, and `develop` branches
- All pull requests to `main`, `master`, and `develop` branches

#### Jobs

1. **test**: Runs the test suite on multiple Python versions (3.8, 3.9, 3.10, 3.11)
   - Uses `uv` for fast dependency management
   - Warnings are treated as non-fatal (don't fail the build)
   - Test results are uploaded as artifacts

2. **test-coverage**: Generates test coverage reports using Python 3.11
   - Creates HTML and XML coverage reports
   - Uploads coverage reports as artifacts

3. **lint**: Code quality checks (optional - won't fail the build)
   - Black code formatting check
   - isort import sorting check
   - flake8 linting
   - All linting steps use `continue-on-error: true` to not fail the build

#### Configuration

- **Warning Handling**: Warnings are suppressed using `PYTHONWARNINGS=ignore` to ensure they don't clutter CI output or cause build failures
- **Test Configuration**: Uses `pytest.ini` for consistent test behavior
- **Dependency Caching**: uv automatically caches dependencies for faster builds
- **Artifact Retention**: Test results kept for 7 days, coverage reports for 30 days

#### Local Testing

To run the same tests locally that run in CI:

```bash
# Install dependencies
uv sync --extra dev

# Run tests (same as CI)
PYTHONWARNINGS=ignore uv run pytest tests/ -v --tb=short

# Run with coverage
PYTHONWARNINGS=ignore uv run pytest tests/ --cov=asyncmiele --cov-report=html

# Run linting (optional)
uv run black --check asyncmiele/ tests/
uv run isort --check-only asyncmiele/ tests/
uv run flake8 asyncmiele/ tests/
```

## Files

- `test.yml`: Main CI/CD workflow
- `pytest.ini`: Pytest configuration (in project root)
- This README: Documentation 