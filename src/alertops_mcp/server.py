"""FastMCP factory + health endpoint wiring for the AlertOps connector (PRD-21220).

Known pitfalls this file deliberately avoids (see the vendor-mcp-development
SOP §7):

- DNS-rebinding protection is explicitly disabled -- this service sits behind
  the Agent Gateway, not exposed directly, so a non-localhost Host header is
  expected on every request and must not be rejected with 421.
- The MCP app's lifespan is wired to the *outer* Starlette app explicitly
  (``lifespan=mcp_app.router.lifespan_context``); ``Mount()`` alone does not
  run a mounted sub-app's lifespan, which otherwise surfaces as
  "Task group is not initialized" on the first ``/mcp`` call while ``/health``
  keeps returning 200.
- ``stateless_http=True`` so no client is required to keep hitting the same
  replica (the Gateway may run several, and a request isn't guaranteed to
  land on the one that handled ``initialize``).
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .middleware import CREDENTIAL_HEADER, CredentialMiddleware
from .tools import register as register_tools

INSTRUCTIONS = (
    "AlertOps connector: review incident alerts, on-call status, and response "
    "group membership for the tenant's AlertOps account. All tools are "
    "read-only. Typical flow: alertops_get_oncall_now to see who is on call, "
    "alertops_list_alerts (optionally filtered by status/priority/group) to "
    "see open work, alertops_get_alert for full detail on one alert, and "
    "alertops_list_groups / alertops_get_group_members for response-group "
    "visibility. alertops_get_group_schedule returns a group's rotation over "
    "a date range of at most 3 months."
)


class ServerSettings(BaseSettings):
    """Non-credential configuration only -- the AlertOps API key always
    comes from the per-request ``X-AlertOps-Api-Key`` header (§3.1 of the SOP),
    never from the environment.
    """

    model_config = SettingsConfigDict(extra="ignore")

    mcp_http_host: str = "0.0.0.0"
    mcp_http_port: int = 8080


def create_app() -> Starlette:
    settings = ServerSettings()

    mcp = FastMCP(
        name="alertops-mcp",
        instructions=INSTRUCTIONS,
        host=settings.mcp_http_host,
        port=settings.mcp_http_port,
        stateless_http=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    register_tools(mcp)

    mcp_app = mcp.streamable_http_app()

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app = Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Mount("/", app=mcp_app),
        ],
        middleware=[Middleware(CredentialMiddleware, mcp_path="/mcp")],
        # Mount() does not propagate a sub-app's lifespan -- wire it explicitly
        # so the MCP session manager actually starts (see module docstring).
        lifespan=mcp_app.router.lifespan_context,
    )
    return app


__all__ = ["create_app", "CREDENTIAL_HEADER"]
