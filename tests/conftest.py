from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.getenv("PROBALYTICS_RUN_INTEGRATION") == "1":
        return

    skip_integration = pytest.mark.skip(reason="set PROBALYTICS_RUN_INTEGRATION=1 to run integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
