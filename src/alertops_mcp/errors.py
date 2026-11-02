"""Structured error envelope for AlertOps MCP tools.

Tools never raise -- every failure is returned as a JSON string shaped like
``{"error": {"code": ..., "message": ..., "retryable": ...}}`` so the calling
agent can branch on ``code`` and decide whether to retry (PRD-21220).
"""

from __future__ import annotations

import json

# Fixed, finite error code vocabulary -- do not invent new codes.
ErrorCode = str

NOT_CONFIGURED = "not_configured"
UNAUTHORIZED = "unauthorized"
NOT_FOUND = "not_found"
INVALID_ARGUMENT = "invalid_argument"
RATE_LIMITED = "rate_limited"
UPSTREAM_ERROR = "upstream_error"

_RETRYABLE = {RATE_LIMITED, UPSTREAM_ERROR}

# AlertOps HTTP status -> our error code.
_STATUS_TO_CODE: dict[int, ErrorCode] = {
    400: INVALID_ARGUMENT,
    401: UNAUTHORIZED,
    403: UNAUTHORIZED,
    404: NOT_FOUND,
    422: INVALID_ARGUMENT,
    429: RATE_LIMITED,
}


class AlertOpsApiError(Exception):
    """Raised by the API client; carries enough to map to the envelope."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def code_for_status(status_code: int) -> ErrorCode:
    # Anything not explicitly mapped (incl. our own 599 timeout/network sentinel
    # and any other 5xx) is a retryable upstream failure.
    return _STATUS_TO_CODE.get(status_code, UPSTREAM_ERROR)


def error_envelope(code: ErrorCode, message: str) -> str:
    """Serialize a structured error as a compact JSON string (tool return value)."""
    body = {"error": {"code": code, "message": message, "retryable": code in _RETRYABLE}}
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"))


def envelope_for_exception(exc: Exception) -> str:
    """Map any exception raised while calling AlertOps to the error envelope."""
    if isinstance(exc, AlertOpsApiError):
        return error_envelope(code_for_status(exc.status_code), exc.message)
    # Network errors, timeouts, anything unforeseen: treat as a retryable
    # upstream failure, never leak the raw exception text to the caller.
    return error_envelope(UPSTREAM_ERROR, f"AlertOps request failed: {exc.__class__.__name__}")
