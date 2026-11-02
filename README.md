# alertops-mcp

MCP server for [AlertOps](https://www.alertops.com/), an incident-paging platform. Exposes
read-only tools for alerts, on-call status, and response-group visibility to the MSPbots
Agent Platform.

- Transport: MCP Streamable HTTP (`POST /mcp`), stateless.
- Stack: Python 3.12, FastMCP, httpx.
- License: proprietary (internal MSPbots connector).

---

<div align="center">

## MSPbots Connector

**The MCP Gateway built for MSPs: visible, controlled, and your data stays where it belongs.**

[**Get started at connect.mspbots.ai →**](https://connect.mspbots.ai)

</div>

---

MSPbots Connector gives your AI clients one MCP URL to reach your entire MSP stack (RMM, PSA, documentation, security, finance), and gives you control over who can call which tool and a record of everything that was called.

**Hosted service: [connect.mspbots.ai](https://connect.mspbots.ai)** · Free to use.

### Why Connector

![MSPbots Connector](https://stgoss.mspbots.ai/files/mcp/mspbots-mcp.png)

| | |
|---|---|
| **Visible** | Every tool call is logged: who, which vendor, when. Usage dashboard, CSV export, SIEM streaming. |
| **Controlled** | Role-based, per-tool allowlist. Deny by default. |
| **Protected** | Credentials encrypted per record. AI clients never see your vendor passwords or tokens. |
| **MSP-native** | Built for the MSP stack only: RMM, PSA, documentation, security, finance. |

### Quick start

1. **Sign up** at [connect.mspbots.ai](https://connect.mspbots.ai).
2. **Connect your vendors.** Pick from 150+ connectors and authorize each one on the vendor's own page, or bring your own API keys. No extra vendor accounts needed.
3. **Set access.** Create roles and decide which tools each role may call. Nothing is allowed until you allow it.
4. **Add your MCP URL to your AI client.** Copy the URL from your Connector dashboard into Claude, ChatGPT, Cursor, VS Code, Gemini, Codex, or any MCP-capable client.
5. **Ask your AI to do real work**, and watch every call appear in the audit log.

### Features

**Unified gateway**
- One MCP URL for all your AI clients
- 150+ connectors across the MSP stack
- Custom MCP servers supported, free
- Authorization happens on each vendor's own page; the AI never sees passwords or tokens
- Bring your own credentials: use the vendor API keys you already have
- Multiple accounts per app; connect once, reuse across AI clients
- Tool search: finds the right action for the task
- One sign-in; vendor credentials are injected behind the scenes and OAuth tokens refresh automatically

**Visibility**
- Audit log for every tool call (who, which vendor, when)
- Usage dashboard: call volume, top vendors, error rate, per-user activity
- Export audit logs to CSV, or stream to Loki, Graylog, or LogScale (SIEM)
- Optional recording of tool arguments and result summaries (off by default, enabled per organization)

**Control**
- Per-role, per-tool allowlist, deny by default
- owner / admin / member roles
- SCIM provisioning with Entra ID, Okta, JumpCloud, and Google Workspace

**Security**
- Credentials encrypted one record at a time (AES-256-GCM, per-record key)
- AI clients authenticate with OAuth 2.1 + PKCE
- Vendor responses are scanned for prompt-injection patterns and returned as structured data. This is one layer of defense, not a guarantee against every attack.
- Static egress IP for customer firewall and API allowlisting

### Pricing

**Free.**

Links: [connect.mspbots.ai](https://connect.mspbots.ai) · [mspbots.ai](https://mspbots.ai)

---

## Authentication headers

| Header | Required | Meaning |
|---|---|---|
| `X-AlertOps-Api-Key` | yes | AlertOps User API key. Sent to AlertOps as the `api-key` header on every upstream call. Generate it in AlertOps under your profile → API Key. |

## Tools

All tools are read-only (`readOnlyHint: true`). None create, update, close, assign, or delete anything in AlertOps.

| Tool | Description |
|---|---|
| `alertops_list_alerts` | List alerts, optionally filtered by status, priority, group, or creation date range. Paginated. |
| `alertops_get_alert` | Get full detail for one alert by id (status, owner, escalation policy, SLA state). |
| `alertops_list_groups` | List response groups, optionally filtered by a name search term. Paginated. |
| `alertops_get_group_members` | List a response group's members (name, type, roles). |
| `alertops_get_oncall_now` | Get who is on call right now, for one group or for every group. |
| `alertops_get_group_schedule` | Get a group's on-call schedule/rotation over a date range of at most 3 months. |

See AlertOps' [integration overview](https://help.alertops.com/knowledge-base/integration-overview) for background on the vendor API this connector calls.

## Local development

```bash
uv sync --extra dev
uv run pytest
uv run python -m alertops_mcp          # listens on 0.0.0.0:8080
```

Manual end-to-end check (replace the header value with a real AlertOps API key):

```bash
curl -X POST http://localhost:8080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'X-AlertOps-Api-Key: ak_your_key_here' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Docker

```bash
docker build --platform linux/amd64 -t alertops-mcp:dev .
docker run --rm -p 8080:8080 alertops-mcp:dev
```
