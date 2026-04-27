# Dwar Rater — TDD Workflow Guide

## Rule: No code without a test

Every new feature or bugfix follows the Red-Green-Refactor cycle:

1. **Red** — Write one failing test first
2. **Green** — Write the minimal code to make it pass
3. **Refactor** — Clean up, rerun tests after every change

## Test data policy

- **Use fixtures, not live requests.** All tests must work with pre-saved JSON fixtures in `tests/fixtures/`.
- Never make HTTP requests to `dwar.ru` or any external service in tests.
- Fixtures are created once from real data, then committed to the repo.

## Running tests

```bash
# All tests
cd backend && pytest

# Single file
pytest tests/test_auth.py -v

# With coverage
pip install pytest-cov
pytest --cov=. --cov-report=term-missing

# Watch mode (auto-rerun on change)
pip install pytest-watch
ptw
```

## Pre-commit hook

The pre-commit hook runs all tests before allowing a commit. To install:

```bash
# From project root:
cp backend/hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

To skip (emergency only): `git commit --no-verify`

## Fixture conventions

- `tests/fixtures/` — JSON files with saved parser output, API responses, etc.
- Naming: `<feature>_<description>.json`
- Load in tests via the `fixture_data` pytest fixture:
  ```python
  def test_something(fixture_data):
      data = fixture_data("analyze_full_profile")
      assert data["nick"] == "TestNick"
  ```
