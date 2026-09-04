# instant-mongo

MongoDB runner for integration tests.

## Workflow

- Before committing, always run `make lint` and `make check` and fix any errors.
- Do not add a `Claude-Session:` line (or any session URL) to commit messages.

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
- Create git tag: `git tag vX.Y.Z` and push it: `git push origin vX.Y.Z`

Pushing the tag triggers `.github/workflows/release.yml`, which builds the wheel
and sdist, checks that the package version matches the tag, and creates a GitHub
Release with both files attached. The workflow can also be run manually
(`workflow_dispatch`) for an existing tag.
