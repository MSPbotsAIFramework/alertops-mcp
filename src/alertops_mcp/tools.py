"""The six read-only AlertOps tools (PRD-21220).

Each tool: validates its own arguments, builds an :class:`AlertOpsClient`
from the request-scoped credential, calls AlertOps, and returns a compact
JSON string -- either the result or the structured error envelope. No tool
raises to the MCP protocol layer.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import AlertOpsClient
from .errors import INVALID_ARGUMENT, NOT_CONFIGURED, envelope_for_exception, error_envelope
from .middleware import current_api_key

LIST_LIMIT_DEFAULT = 20
LIST_LIMIT_HARD_CAP = 100
SCHEDULE_MAX_WINDOW_DAYS = 92  # AlertOps documents a 3-month maximum window.


def _dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _client() -> AlertOpsClient | None:
    api_key = current_api_key()
    if not api_key:
        return None
    return AlertOpsClient(api_key)


def _clamp_limit(limit: int) -> int:
    return max(1, min(int(limit), LIST_LIMIT_HARD_CAP))


def _parse_date(value: str, field: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date (YYYY-MM-DD)") from exc


def register(mcp: FastMCP) -> None:
    """Register all six AlertOps tools on the given FastMCP instance."""

    @mcp.tool(annotations={"readOnlyHint": True})
    async def alertops_list_alerts(
        status: str | None = None,
        priority: str | None = None,
        group: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
        limit: int = LIST_LIMIT_DEFAULT,
        offset: int = 0,
    ) -> str:
        """List AlertOps alerts for the tenant, newest first.

        Args:
            status: Filter by alert status (e.g. "Open", "Assigned", "Closed").
            priority: Filter by priority (e.g. "Critical", "High").
            group: Filter by response group name.
            created_from: Only alerts created on/after this date (YYYY-MM-DD).
            created_to: Only alerts created on/before this date (YYYY-MM-DD).
            limit: Max alerts to return (default 20, hard cap 100).
            offset: Pagination offset.
        """
        client = _client()
        if client is None:
            return error_envelope(NOT_CONFIGURED, "No AlertOps credential available")
        try:
            limit = _clamp_limit(limit)
            data = await client.get(
                "/alerts",
                {
                    "status": status,
                    "priority": priority,
                    "group": group,
                    "created_from": created_from,
                    "created_to": created_to,
                    "limit": limit,
                    "offset": offset,
                },
            )
            alerts = data.get("alerts", data if isinstance(data, list) else [])
            return _dumps(
                {
                    "alerts": alerts,
                    "limit": limit,
                    "offset": offset,
                    "has_more": bool(data.get("has_more", len(alerts) == limit)) if isinstance(data, dict) else len(alerts) == limit,
                }
            )
        except Exception as exc:  # noqa: BLE001 - mapped to a structured envelope, never re-raised
            return envelope_for_exception(exc)

    @mcp.tool(annotations={"readOnlyHint": True})
    async def alertops_get_alert(alert_id: str) -> str:
        """Get full detail for one AlertOps alert by id.

        Args:
            alert_id: The AlertOps alert id.
        """
        client = _client()
        if client is None:
            return error_envelope(NOT_CONFIGURED, "No AlertOps credential available")
        try:
            data = await client.get(f"/alerts/{alert_id}")
            return _dumps(data)
        except Exception as exc:  # noqa: BLE001
            return envelope_for_exception(exc)

    @mcp.tool(annotations={"readOnlyHint": True})
    async def alertops_list_groups(
        search: str | None = None,
        limit: int = LIST_LIMIT_DEFAULT,
        offset: int = 0,
    ) -> str:
        """List the tenant's AlertOps response groups.

        Args:
            search: Only return groups whose name matches this term.
            limit: Max groups to return (default 20, hard cap 100).
            offset: Pagination offset.
        """
        client = _client()
        if client is None:
            return error_envelope(NOT_CONFIGURED, "No AlertOps credential available")
        try:
            limit = _clamp_limit(limit)
            data = await client.get("/groups", {"search": search, "limit": limit, "offset": offset})
            groups = data.get("groups", data if isinstance(data, list) else [])
            return _dumps(
                {
                    "groups": groups,
                    "limit": limit,
                    "offset": offset,
                    "has_more": bool(data.get("has_more", len(groups) == limit)) if isinstance(data, dict) else len(groups) == limit,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return envelope_for_exception(exc)

    @mcp.tool(annotations={"readOnlyHint": True})
    async def alertops_get_group_members(group_id: str) -> str:
        """List the members of one AlertOps response group (who is in it, their role).

        Args:
            group_id: The AlertOps group id.
        """
        client = _client()
        if client is None:
            return error_envelope(NOT_CONFIGURED, "No AlertOps credential available")
        try:
            data = await client.get(f"/groups/{group_id}/members")
            members = data.get("members", data if isinstance(data, list) else [])
            return _dumps({"members": members})
        except Exception as exc:  # noqa: BLE001
            return envelope_for_exception(exc)

    @mcp.tool(annotations={"readOnlyHint": True})
    async def alertops_get_oncall_now(group_id: str | None = None) -> str:
        """Get who is on call right now, for one group or for every group.

        Args:
            group_id: Scope to one AlertOps group id; omit for all groups.
        """
        client = _client()
        if client is None:
            return error_envelope(NOT_CONFIGURED, "No AlertOps credential available")
        try:
            data = await client.get("/schedules/oncallnow", {"group_id": group_id})
            return _dumps(data if isinstance(data, dict) else {"groups": data})
        except Exception as exc:  # noqa: BLE001
            return envelope_for_exception(exc)

    @mcp.tool(annotations={"readOnlyHint": True})
    async def alertops_get_group_schedule(group_id: str, start_date: str, end_date: str) -> str:
        """Get a group's on-call schedule/rotation over a date range (max 3 months).

        Args:
            group_id: The AlertOps group id.
            start_date: Window start, inclusive (YYYY-MM-DD).
            end_date: Window end, inclusive (YYYY-MM-DD). Must be within 3 months of start_date.
        """
        client = _client()
        if client is None:
            return error_envelope(NOT_CONFIGURED, "No AlertOps credential available")
        try:
            start = _parse_date(start_date, "start_date")
            end = _parse_date(end_date, "end_date")
        except ValueError as exc:
            return error_envelope(INVALID_ARGUMENT, str(exc))
        if end < start:
            return error_envelope(INVALID_ARGUMENT, "end_date must not be before start_date")
        if (end - start) > timedelta(days=SCHEDULE_MAX_WINDOW_DAYS):
            return error_envelope(INVALID_ARGUMENT, "Date range must not exceed 3 months")
        try:
            data = await client.get(
                f"/schedules/{group_id}",
                {"start_date": start_date, "end_date": end_date},
            )
            schedules = data.get("schedules", data if isinstance(data, list) else [])
            return _dumps({"schedules": schedules})
        except Exception as exc:  # noqa: BLE001
            return envelope_for_exception(exc)
