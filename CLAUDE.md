# instant-mongo

MongoDB runner for integration tests.

## Workflow

- Before committing, always run `make lint` and `make check` and fix any errors.
- Do not add a `Claude-Session:` line (or any session URL) to commit messages.

## Commands

- Run tests: `uv run pytest`
- Run single test: `uv run pytest tests/test_basic_usage.py::test_name -v`
- Run all tests verbose: `make`

## Changelog

- `README.md` has a `Changelog` section. The topmost entry is `### Development version`
  and collects changes since the last release.
- Whenever you make a user-visible change (behaviour, API, parameters, CLI, dependencies,
  supported versions), add a bullet to `### Development version`. Put breaking changes
  under a `**Breaking changes:**` sub-heading within that entry.
- If the entry only contains the `- No changes yet` placeholder, replace the placeholder
  with the first real bullet.

## Releasing

Version is defined in two places — keep them in sync:
- `pyproject.toml` (`version = "x.y.z"`)
- `instant_mongo/__init__.py` (`__version__ = 'x.y.z'`)

Also update `README.md`:
- installation URLs (3 places)
- changelog: rename `### Development version` to `### x.y.z (YYYY-MM-DD)`, then add a new
  empty `### Development version` entry above it with the `- No changes yet` placeholder

Commit on `master`, then create the git tag and push it:
`git tag vX.Y.Z && git push origin master vX.Y.Z`

Pushing the tag triggers `.github/workflows/release.yml`, which builds the wheel
and sdist, checks that the package version matches the tag, and creates a GitHub
Release with both files attached. The workflow can also be run manually
(`workflow_dispatch`) for an existing tag.
