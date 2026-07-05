# Contributing

## Development

Install development dependencies:

```bash
uv sync --extra test
```

Run the standard test suite:

```bash
uv run --extra test pytest
```

Run ClickHouse integration tests with Docker:

```bash
PROBALYTICS_RUN_INTEGRATION=1 uv run --extra test pytest tests/test_clickhouse_integration.py
```

## Pull Requests

- Keep changes focused.
- Add or update tests for behavior changes.
- Update README examples when public API behavior changes.
- Confirm unit tests pass before requesting review.
