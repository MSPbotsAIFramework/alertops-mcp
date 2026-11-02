"""Unit tests for the six AlertOps tools (PRD-21220).

Each test is anchored to one TC-AOPS-xxx id from docs/tickets/PRD-21220.ac.json.
AlertOps itself is mocked with respx -- these never touch the network.
"""

from __future__ import annotations

import respx
from httpx import Response

from .conftest import get_tool, loads

BASE = "https://api.alertops.com/api/v2"


# -- TC-AOPS-001 / AC1: list alerts, paginated, default page size -----------
@respx.mock
async def test_list_alerts_returns_paginated_results(mcp, with_api_key):
    with_api_key()
    respx.get(f"{BASE}/alerts").mock(
        return_value=Response(
            200,
            json={
                "alerts": [
                    {"alert_id": 1, "status": "Open", "priority": "Critical", "owner": {"user_name": "jdoe"}, "created_date": "2026-01-01T00:00:00"}
                ],
                "has_more": False,
            },
        )
    )
    fn = get_tool(mcp, "alertops_list_alerts")
    result = loads(await fn())
    assert result["limit"] == 20
    assert result["offset"] == 0
    assert result["has_more"] is False
    assert result["alerts"][0]["alert_id"] == 1


# -- TC-AOPS-002 / AC2: status + priority filters are both applied ----------
@respx.mock
async def test_list_alerts_filters_by_status_and_priority(mcp, with_api_key):
    with_api_key()
    route = respx.get(f"{BASE}/alerts").mock(
        return_value=Response(200, json={"alerts": [], "has_more": False})
    )
    fn = get_tool(mcp, "alertops_list_alerts")
    await fn(status="Open", priority="Critical")
    sent = route.calls.last.request
    assert sent.url.params["status"] == "Open"
    assert sent.url.params["priority"] == "Critical"


# -- TC-AOPS-003 / AC3: get alert returns full detail ------------------------
@respx.mock
async def test_get_alert_returns_full_detail(mcp, with_api_key):
    with_api_key()
    respx.get(f"{BASE}/alerts/51296").mock(
        return_value=Response(
            200,
            json={
                "alert_id": 51296,
                "status": "Assigned",
                "owner": {"user_name": "jdoe"},
                "escalation_policy": "Default",
                "within_sla": True,
            },
        )
    )
    fn = get_tool(mcp, "alertops_get_alert")
    result = loads(await fn(alert_id="51296"))
    assert result["status"] == "Assigned"
    assert result["escalation_policy"] == "Default"


# -- TC-AOPS-004 / AC3: unknown alert id -> structured not_found ------------
@respx.mock
async def test_get_alert_not_found_returns_structured_error(mcp, with_api_key):
    with_api_key()
    respx.get(f"{BASE}/alerts/does-not-exist").mock(
        return_value=Response(404, json={"message": "Alert not found"})
    )
    fn = get_tool(mcp, "alertops_get_alert")
    result = loads(await fn(alert_id="does-not-exist"))
    assert result["error"]["code"] == "not_found"
    assert result["error"]["retryable"] is False


# -- TC-AOPS-005 / AC4: list groups, paginated -------------------------------
@respx.mock
async def test_list_groups_returns_paginated_results(mcp, with_api_key):
    with_api_key()
    respx.get(f"{BASE}/groups").mock(
        return_value=Response(200, json={"groups": [{"group_id": 1000, "group_name": "Support"}], "has_more": False})
    )
    fn = get_tool(mcp, "alertops_list_groups")
    result = loads(await fn())
    assert result["groups"][0]["group_name"] == "Support"


# -- TC-AOPS-006 / AC4: search term narrows group list -----------------------
@respx.mock
async def test_list_groups_search_filters_by_name(mcp, with_api_key):
    with_api_key()
    route = respx.get(f"{BASE}/groups").mock(
        return_value=Response(200, json={"groups": [], "has_more": False})
    )
    fn = get_tool(mcp, "alertops_list_groups")
    await fn(search="Support")
    assert route.calls.last.request.url.params["search"] == "Support"


# -- TC-AOPS-007 / AC5: group members include name/type/roles ---------------
@respx.mock
async def test_get_group_members_returns_roles(mcp, with_api_key):
    with_api_key()
    respx.get(f"{BASE}/groups/1000/members").mock(
        return_value=Response(
            200,
            json={"members": [{"member_id": 1, "member_type": "User", "member": "testuser1", "roles": ["Primary"]}]},
        )
    )
    fn = get_tool(mcp, "alertops_get_group_members")
    result = loads(await fn(group_id="1000"))
    assert result["members"][0]["roles"] == ["Primary"]


# -- TC-AOPS-008 / AC5: empty group -> empty list, not an error -------------
@respx.mock
async def test_get_group_members_empty_group_returns_empty_list(mcp, with_api_key):
    with_api_key()
    respx.get(f"{BASE}/groups/9999/members").mock(return_value=Response(200, json={"members": []}))
    fn = get_tool(mcp, "alertops_get_group_members")
    result = loads(await fn(group_id="9999"))
    assert result == {"members": []}


# -- TC-AOPS-009 / AC6: on-call-now with no group returns all groups --------
@respx.mock
async def test_oncall_now_without_group_returns_all_groups(mcp, with_api_key):
    with_api_key()
    respx.get(f"{BASE}/schedules/oncallnow").mock(
        return_value=Response(
            200,
            json={"groups": [{"group_id": 1, "members": [{"name": "A"}]}, {"group_id": 2, "members": [{"name": "B"}]}]},
        )
    )
    fn = get_tool(mcp, "alertops_get_oncall_now")
    result = loads(await fn())
    assert len(result["groups"]) == 2


# -- TC-AOPS-010 / AC6: on-call-now with a group id scopes to that group ----
@respx.mock
async def test_oncall_now_with_group_id_filters_to_one_group(mcp, with_api_key):
    with_api_key()
    route = respx.get(f"{BASE}/schedules/oncallnow").mock(
        return_value=Response(200, json={"groups": [{"group_id": 4649, "members": [{"name": "Joe"}]}]})
    )
    fn = get_tool(mcp, "alertops_get_oncall_now")
    result = loads(await fn(group_id="4649"))
    assert result["groups"][0]["group_id"] == 4649
    assert route.calls.last.request.url.params["group_id"] == "4649"


# -- TC-AOPS-011 / AC7: schedule within 3 months returns entries ------------
@respx.mock
async def test_group_schedule_returns_entries_in_range(mcp, with_api_key):
    with_api_key()
    respx.get(f"{BASE}/schedules/1000").mock(
        return_value=Response(200, json={"schedules": [{"schedule_id": "1111", "schedule_type": "Rotating"}]})
    )
    fn = get_tool(mcp, "alertops_get_group_schedule")
    result = loads(await fn(group_id="1000", start_date="2026-01-01", end_date="2026-02-01"))
    assert result["schedules"][0]["schedule_id"] == "1111"


# -- TC-AOPS-012 / AC7: client-side rejection of an out-of-range window -----
# (The real-vendor half of this case -- confirming AlertOps' own upstream
# rejection shape -- needs a live account; see docs/tickets/PRD-21220.md
# "Decisions made by DEV01" and the Self-test section. This test covers the
# part we can verify without one: our own pre-validation never calls AlertOps.)
async def test_group_schedule_rejects_window_over_three_months(mcp, with_api_key):
    with_api_key()
    fn = get_tool(mcp, "alertops_get_group_schedule")
    result = loads(await fn(group_id="1000", start_date="2026-01-01", end_date="2026-06-01"))
    assert result["error"]["code"] == "invalid_argument"


# -- TC-AOPS-014 / AC8: upstream 401 maps to the structured envelope --------
@respx.mock
async def test_upstream_unauthorized_maps_to_structured_error(mcp, with_api_key):
    with_api_key()
    respx.get(f"{BASE}/alerts").mock(return_value=Response(401, json={"message": "Invalid API key"}))
    fn = get_tool(mcp, "alertops_list_alerts")
    result = loads(await fn())
    assert result["error"]["code"] == "unauthorized"
    assert result["error"]["retryable"] is False


# -- TC-AOPS-015 / AC8: upstream 429 / 5xx map to rate_limited / upstream_error
@respx.mock
async def test_upstream_rate_limited_maps_after_retries_exhausted(mcp, with_api_key):
    with_api_key()
    respx.get(f"{BASE}/alerts").mock(return_value=Response(429, headers={"Retry-After": "0"}))
    fn = get_tool(mcp, "alertops_list_alerts")
    result = loads(await fn())
    assert result["error"]["code"] == "rate_limited"
    assert result["error"]["retryable"] is True


@respx.mock
async def test_upstream_server_error_maps_to_upstream_error(mcp, with_api_key):
    with_api_key()
    respx.get(f"{BASE}/alerts/500-alert").mock(return_value=Response(503))
    fn = get_tool(mcp, "alertops_get_alert")
    result = loads(await fn(alert_id="500-alert"))
    assert result["error"]["code"] == "upstream_error"
    assert result["error"]["retryable"] is True


# -- not_configured: tool called with no credential in context -------------
async def test_tool_without_credential_returns_not_configured(mcp):
    fn = get_tool(mcp, "alertops_list_alerts")
    result = loads(await fn())
    assert result["error"]["code"] == "not_configured"


# -- tools/list snapshot: six tools, all read-only --------------------------
def test_tools_list_snapshot(mcp):
    tools = mcp._tool_manager.list_tools()
    names = sorted(t.name for t in tools)
    assert names == [
        "alertops_get_alert",
        "alertops_get_group_members",
        "alertops_get_group_schedule",
        "alertops_get_oncall_now",
        "alertops_list_alerts",
        "alertops_list_groups",
    ]
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
