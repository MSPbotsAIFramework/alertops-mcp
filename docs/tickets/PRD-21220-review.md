# PRD-21220 · Code review

Status: frozen @ 845fd90

## Round 1 · 2026-11-02 · reviewed dev/PRD-21220 @ 845fd90 (base main @ 9453815)

Verdict: approved

### Scope

Brand-new repository (`MSPbotsAIFramework/alertops-mcp`), single repo, `Track: vendor-mcp`, `Release order: any`. Diff is `main@9453815...dev/PRD-21220@845fd90` (20 files, all new — see Change list below). `main` has not moved since the design pass, so this is the full diff to review, not an increment.

Files reviewed: `src/alertops_mcp/{__init__,__main__,server,middleware,client,errors,tools}.py`, `tests/{conftest,test_tools,test_middleware}.py`, `pyproject.toml`, `uv.lock`, `Dockerfile`, `.dockerignore`, `.gitignore`, `.python-version`, `README.md`, `docs/tickets/PRD-21220.{md,ac.json}`.

### Findings

No must-fix findings.

1. [suggestion] `src/alertops_mcp/tools.py:93-96` and `:142-144` — the `has_more` computation (`bool(data.get("has_more", len(alerts) == limit)) if isinstance(data, dict) else len(alerts) == limit`) is duplicated verbatim between `alertops_list_alerts` and `alertops_list_groups`. Pulling it into a small helper (e.g. `_has_more(data, items, limit)` in the same module) would remove the duplication without changing behavior. Not a release blocker — both call sites are correct and covered by tests (TC-AOPS-001/005).

### Verification performed

- Ran the gate myself on the reviewed commit (not just trusting the Self-test section): `uv sync --extra dev && uv run pytest -q` → `21 passed in 6.41s`, matching the Self-test section and `ac.json` evidence exactly.
- `grep -rnP '[\x{4e00}-\x{9fff}]' --exclude-dir=.git --exclude-dir=.venv .` → no output (no Chinese anywhere in the repo), confirming the Self-test claim independently.
- Diffed `README.md`'s "MSPbots Connector" section against `~/.claude/skills/vendor-mcp-development/reference/readme-connector-section.md` byte-for-byte (`diff`) → identical, confirming the Self-test claim independently.
- Walked the SOP §14 delivery checklist (contract, errors/network, container, agent-facing design, logging) against the code: credential only from `X-AlertOps-Api-Key` header via a `contextvars.ContextVar` reset in a `finally` block (`middleware.py:60-65`, AC9); DNS-rebinding protection explicitly disabled with a documented reason (`server.py:66`); MCP app lifespan wired to the outer Starlette app (`server.py:82-83`); `/health` reachable without the credential header (`middleware.py:43-44`, `test_middleware.py:69-76`); structured error envelope with a fixed code vocabulary, no raw exception ever returned to a tool caller (`errors.py`, every tool in `tools.py` wraps its body in `try/except Exception`); connect/read timeouts and bounded retry with `Retry-After` handling on 429/5xx (`client.py:19-21,60-66`); one `httpx.AsyncClient` per call, reused across that call's retries, not pooled across requests (`client.py:44`); Dockerfile is multi-stage, non-root (`app`, uid/gid 1001), installs `curl` for the `HEALTHCHECK`, `EXPOSE 8080` with matching default envs; all 6 tools carry `readOnlyHint: true` and a `alertops_` prefix; list tools default `limit=20`/hard cap `100`, both within the SOP's ≤50/≤200 guidance; `tests/test_tools.py::test_tools_list_snapshot` locks the tool set and the read-only annotation.
- Compared the six tools, their parameters, and the error envelope shape against the tech design's "Tools" and "Data & API contract" tables — match exactly; no undocumented tool, parameter, or endpoint.
- Compared the test list in `ac.json` against `tests/test_tools.py` / `tests/test_middleware.py` — every `tests` entry resolves to a real, passing test function; the one case not fully automated (TC-AOPS-012) has its client-side half covered by `test_group_schedule_rejects_window_over_three_months` and its upstream-only half honestly recorded as `"result": "blocked"` with a reason (needs a real AlertOps account), not silently marked pass.
- No migration, no DROP, no database — not applicable to this service.
- Reuse check: `fastmcp`, `httpx`, `pydantic`/`pydantic-settings` are the SOP's own recommended stack for a new Python MCP service (per the tech design's "Reuse & cleanup" section); no hand-rolled HTTP client, retry loop, or JSON-RPC framing found.
