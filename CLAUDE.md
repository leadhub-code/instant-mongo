# instant-mongo

MongoDB runner for integration tests.

## Workflow

- Before committing, always run `make lint` and `make check` and fix any errors.

## Commands

- Run tests: `uv run pytest`
- Run single test: `uv run pytest tests/test_basic_usage.py::test_name -v`
- Run all tests verbose: `make`

## Releasing

Version is defined in two places — keep them in sync:
- `pyproject.toml` (`version = "x.y.z"`)
- `instant_mongo/__init__.py` (`__version__ = 'x.y.z'`)

Also update:
- `README.md` — installation URLs (3 places) and changelog
- Create git tag: `git tag vX.Y.Z`
