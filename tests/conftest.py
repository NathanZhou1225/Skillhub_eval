import os

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "requires_local_agent: needs installed CLI agent (claude/codex/cursor-agent)",
    )


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_LOCAL_AGENT") == "1":
        return
    skip = pytest.mark.skip(reason="set RUN_LOCAL_AGENT=1 to run local agent E2E tests")
    for item in items:
        if "requires_local_agent" in item.keywords:
            item.add_marker(skip)
