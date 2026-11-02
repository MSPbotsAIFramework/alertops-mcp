"""Entry point: run the AlertOps MCP server with uvicorn (PRD-21220)."""

from __future__ import annotations

import os

import uvicorn

from .server import create_app

app = create_app()


def main() -> None:
    host = os.environ.get("MCP_HTTP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_HTTP_PORT", "8080"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
