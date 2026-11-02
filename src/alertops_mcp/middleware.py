"""Request-scoped credential handling (PRD-21220).

The AlertOps API key arrives per-request in the ``X-AlertOps-Api-Key``
header. It is stored in a ``contextvars.ContextVar`` for the lifetime of the
request only -- never in a module-level variable, never cached across
requests -- so concurrent requests from different tenants can never observe
each other's credential (AC9).
"""

from __future__ import annotations

from contextvars import ContextVar

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

CREDENTIAL_HEADER = "X-AlertOps-Api-Key"

_api_key: ContextVar[str | None] = ContextVar("alertops_api_key", default=None)


def current_api_key() -> str | None:
    """Return the AlertOps API key for the in-flight request, if any."""
    return _api_key.get()


class CredentialMiddleware(BaseHTTPMiddleware):
    """Reads the AlertOps credential header and scopes it to this request.

    Only guards the MCP endpoint -- ``/health`` must stay reachable without
    a credential header so the container health probe never depends on a
    tenant key.
    """

    def __init__(self, app: ASGIApp, mcp_path: str = "/mcp") -> None:
        super().__init__(app)
        self._mcp_path = mcp_path

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith(self._mcp_path):
            return await call_next(request)

        api_key = request.headers.get(CREDENTIAL_HEADER)
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "unauthorized",
                        "message": "Missing required header(s)",
                        "required_headers": [CREDENTIAL_HEADER],
                        "retryable": False,
                    }
                },
            )

        token = _api_key.set(api_key)
        try:
            response: Response = await call_next(request)
        finally:
            _api_key.reset(token)
        return response


def install_credential_middleware(app: Starlette, mcp_path: str = "/mcp") -> None:
    app.add_middleware(CredentialMiddleware, mcp_path=mcp_path)
