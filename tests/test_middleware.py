"""Credential middleware tests (PRD-21220): AC8 (missing header -> 401) and
AC9 (tenant isolation under concurrency).

These exercise ``CredentialMiddleware`` directly against a minimal Starlette
app rather than the full MCP app -- the behavior under test is the header ->
ContextVar plumbing, not the MCP protocol itself.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from alertops_mcp.middleware import CREDENTIAL_HEADER, CredentialMiddleware, current_api_key


async def _echo_key(request):
    # Simulate a tiny bit of work so two concurrent requests actually
    # interleave instead of running start-to-finish back to back.
    await asyncio.sleep(0.01)
    return JSONResponse({"api_key": current_api_key()})


def _build_app() -> Starlette:
    app = Starlette(routes=[Route("/mcp", _echo_key, methods=["POST"])])
    app.add_middleware(CredentialMiddleware, mcp_path="/mcp")
    return app


@pytest.fixture
def client():
    app = _build_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# -- TC-AOPS-013 / AC8: missing header -> 401, no upstream call -------------
async def test_missing_credential_header_returns_401(client):
    async with client:
        response = await client.post("/mcp")
    assert response.status_code == 401
    body = response.json()
    assert CREDENTIAL_HEADER in body["error"]["required_headers"]


async def test_present_credential_header_is_available_to_the_handler(client):
    async with client:
        response = await client.post("/mcp", headers={CREDENTIAL_HEADER: "tenant-a-key"})
    assert response.status_code == 200
    assert response.json()["api_key"] == "tenant-a-key"


# -- TC-AOPS-016 / AC9: concurrent requests never cross tenants -------------
async def test_concurrent_requests_do_not_cross_tenant_credentials(client):
    async with client:
        results = await asyncio.gather(
            client.post("/mcp", headers={CREDENTIAL_HEADER: "tenant-a-key"}),
            client.post("/mcp", headers={CREDENTIAL_HEADER: "tenant-b-key"}),
        )
    keys = sorted(r.json()["api_key"] for r in results)
    assert keys == ["tenant-a-key", "tenant-b-key"]


async def test_health_path_is_reachable_without_a_credential_header():
    app = Starlette(routes=[Route("/health", lambda r: JSONResponse({"status": "ok"}))])
    app.add_middleware(CredentialMiddleware, mcp_path="/mcp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
