"""Thin async wrapper around AlertOps' public v2 REST API (PRD-21220).

One client is built per tool call from the request-scoped credential
(``middleware.current_api_key()``) -- never cached across requests, never
pooled with a baked-in credential, matching the per-request isolation the
SOP requires for a multi-tenant service with no database of its own (AC9).
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from .errors import AlertOpsApiError

BASE_URL = "https://api.alertops.com/api/v2"
CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 30.0
MAX_RETRIES = 3
# Keep a single call's total wall time (connect + reads + backoff) comfortably
# under the 120s budget the SOP sets for one tool invocation.
MAX_TOTAL_SECONDS = 100.0


class AlertOpsClient:
    """Calls AlertOps' v2 API with the given tenant API key."""

    def __init__(self, api_key: str, base_url: str = BASE_URL) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        url = f"{self._base_url}{path}"
        timeout = httpx.Timeout(connect=CONNECT_TIMEOUT, read=READ_TIMEOUT, write=READ_TIMEOUT, pool=READ_TIMEOUT)
        headers = {"api-key": self._api_key, "Accept": "application/json"}

        deadline = asyncio.get_event_loop().time() + MAX_TOTAL_SECONDS
        attempt = 0
        last_exc: Exception | None = None

        async with httpx.AsyncClient(timeout=timeout) as client:
            while attempt < MAX_RETRIES:
                attempt += 1
                try:
                    response = await client.get(url, params=params, headers=headers)
                except httpx.TimeoutException as exc:
                    last_exc = exc
                    raise AlertOpsApiError(599, "Timed out calling AlertOps") from exc
                except httpx.HTTPError as exc:
                    raise AlertOpsApiError(599, "Network error calling AlertOps") from exc

                if response.status_code < 400:
                    if response.status_code == 204 or not response.content:
                        return {}
                    return response.json()

                if response.status_code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining <= 0:
                        break
                    delay = _retry_delay(response, attempt, remaining)
                    await asyncio.sleep(delay)
                    continue

                raise AlertOpsApiError(response.status_code, _safe_message(response))

        raise AlertOpsApiError(599, f"AlertOps request did not complete: {last_exc}")


def _retry_delay(response: httpx.Response, attempt: int, remaining: float) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            delay = float(retry_after)
        except ValueError:
            delay = 2.0**attempt
    else:
        delay = 2.0**attempt
    return max(0.0, min(delay, remaining))


def _safe_message(response: httpx.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict) and "message" in body:
            return str(body["message"])[:500]
    except ValueError:
        pass
    return f"AlertOps returned HTTP {response.status_code}"
