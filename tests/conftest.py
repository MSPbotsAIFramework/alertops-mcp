"""Shared test fixtures (PRD-21220)."""

from __future__ import annotations

import json

import pytest
from mcp.server.fastmcp import FastMCP

from alertops_mcp.middleware import _api_key
from alertops_mcp.tools import register


@pytest.fixture
def mcp() -> FastMCP:
    app = FastMCP(name="alertops-mcp-test")
    register(app)
    return app


def get_tool(mcp: FastMCP, name: str):
    """Return the raw async function behind a registered tool (bypasses the
    MCP protocol envelope -- we want to assert on the JSON string a tool
    returns, not on how FastMCP wraps it into a ContentBlock).
    """
    tool = mcp._tool_manager.get_tool(name)
    assert tool is not None, f"tool {name} is not registered"
    return tool.fn


@pytest.fixture
def with_api_key():
    """Set the request-scoped AlertOps credential for this test.

    Each async test runs as its own asyncio Task with its own copy of the
    context, so setting the var here does not leak into other tests -- no
    reset is needed (and ``ContextVar.reset`` across a fixture's yield
    boundary is unsafe here: pytest-asyncio's async-generator fixture setup
    and teardown are not guaranteed to run in the same Task/Context).
    """

    def setter(value: str = "test-key-123") -> None:
        _api_key.set(value)

    return setter


def loads(result: str) -> dict:
    return json.loads(result)
