# Release Process

## One-Time PyPI Setup

Create a PyPI pending trusted publisher for this project:

- Project name: `probalytics`
- Owner: `Probalytics`
- Repository: `probalytics-python`
- Workflow name: `publish.yml`
- Environment name: `pypi`

The pending publisher creates the PyPI project on first publish if the project
name is still available.

## Publishing

Publish a GitHub release from a version tag:

```bash
git checkout main
git pull --ff-only
git tag v0.1.0
git push origin v0.1.0
gh release create v0.1.0 --title "v0.1.0" --notes "Initial public SDK release"
```

The `Publish` workflow builds the sdist and wheel, then uploads them to PyPI
using Trusted Publishing.

## Before Each Release

- Update `version` in `pyproject.toml`.
- Run `uv build --no-sources`.
- Run `uv run --extra test pytest`.
- Run integration tests when Docker is available:

```bash
PROBALYTICS_RUN_INTEGRATION=1 uv run --extra test pytest tests/test_clickhouse_integration.py
```
