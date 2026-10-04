# Context handoff (condensed from session cb0d90ec, 2026-10-04)

Use this to start a new agent session. Full transcript: `sessions/2026-10-04_session_cb0d90ec.md`.

## The task

STLabs take-home (`STLabs_Agents_TakeHome_Access_Investigation.md`): build a small LLM agent with self-designed tools that investigates employee access in `input_data/access_snapshot.sqlite` (schema guide: `input_data/SCHEMA.md`). Four-hour timebox, proof of concept.

Hard rules: the database stays read-only; no remediation, only recommendations; the OpenRouter key is read from `OPENROUTER_API_KEY` or `token.txt` (gitignored) and never committed; conclusions must cite record or event IDs; submit at least two demo investigations, an architecture write-up, a testing description, limitations, next steps, and all coding-agent transcripts.

Grading priority: agent and tool design, then context management, then evidence vs inference, then scoping, then code quality. Review will ask us to adapt the agent to an unprepared investigation.

## Repo and environment

- Repo: [malcolmessaid/stllabs-takehome](https://github.com/malcolmessaid/stllabs-takehome) (private), branch `master`, latest commit `f408ace`. `gh` is signed in as `malcolmessaid`.
- `input_data/SCHEMA.md` has uncommitted edits that are the user's, not the agent's. Leave it out of commits unless told otherwise.
- Python 3.12 venv in `.venv`; deps are just `openai` and `pydantic` (`requirements.txt`).
- Model: `openai/gpt-5.6-sol` by default (override with `OPENROUTER_MODEL`). Luna (`openai/gpt-5.6-luna`) is about 10x cheaper and handled tests correctly. Key has a $100 limit, about $99.98 left, expires 2026-10-30.

## Commands

```bash
.venv/bin/python entrypoint.py                      # agent chat, clean mode (no logs)
.venv/bin/python entrypoint.py --verbosity mini     # + one log line per tool call
.venv/bin/python entrypoint.py --verbosity verbose  # all logs
.venv/bin/python playground_entrypoint.py           # first row from each repo
.venv/bin/python playground_entrypoint.py llm "prompt"
.venv/bin/python playground_entrypoint.py person "Rowan Mercer"
```

## Architecture (`access_agent/`)

- `db.py`: read-only SQLite singleton (`mode=ro`), `query()` and `query_one()` returning dicts. Uses `sqlite3`, not psycopg2.
- `llm_client.py`: `LLMClient.run(messages, tools=None)` over OpenRouter's OpenAI-compatible API; `get_credit_remaining()` (printed at chat startup in every mode).
- `logger.py`: `get_logger`, `Verbosity` StrEnum (`clean`, `mini`, `verbose`), `configure_logging()`.
- `models/`: Pydantic v2, one file per area (`people`, `identity_provider`, `google_workspace`, `github`, `devices`, `audit_log`), StrEnums instead of Literals, `Field(description=...)` on every field so schemas carry meaning into tool definitions. Plus `person_access.py` (service output) and `report.py` (`InvestigationReport`: summary, findings marked fact or inference with evidence_ids, data_gaps, recommended_actions).
- `repos/`: all SQL lives here. `people_repo`, `identity_provider_repo` (recursive nested-group CTE, app access, assignments), `google_workspace_repo` (nested groups, owned files, unrevoked and unexpired Drive permissions incl. domain), `github_repo` (org, teams, team repo access, unexpired collaborators), `audit_log_repo` (only `get_first_event` so far).
- `services/person_access_service.py`: `find_person(query)`, `list_people(filters, paging)`, `get_person_access(person_id)`.
- `tools/`: one file per tool, each with an args model, a function calling a service, and `TOOL = Tool(...)`. Tools: `list_people`, `find_person`, `get_person_access`, `submit_report`. `registry.py` holds `TOOLS` and `execute_tool` (validates args, returns errors as JSON to the model).
- `agent_service.py`: hand-written tool loop, max 15 steps. Ends when the model calls `submit_report` (returns `InvestigationReport`) or replies in plain text. System prompt carries the snapshot time and schema caveats.
- `entrypoint.py`: interactive chat over `AgentService`, prints reports as sections.
- `docs/idp_connections.html`: tabbed diagrams (IdP, Google Workspace, GitHub) of how access flows.

## Agreed design

- Hand-written loop (no framework), structured final report.
- Tool granularity: purpose-built tools plus a read-only SQL fallback tool (the SQL tool is not built yet). Purpose-built tools encode the tricky joins; SQL covers unprepared review questions, capped at about 50 rows, SELECT only.
- Keep it simple: proof of concept, no over-engineering.

## User conventions

- Don't make unnecessary formatting changes or add extra blank lines; keep comprehensions on one line; lines over 120 chars are fine.
- `logger = get_logger(__name__)` at top of file; log variables as `f"person_id={person_id}"`.
- All database access in repos; services call repos; tools call services.
- Ask before writing tool implementations when the user is still designing; they sometimes want structure only.

## Data facts worth remembering

- Snapshot `2026-08-15T12:00:00Z`. 2,048 people; 2,040 IdP accounts (all linked to a person, none suspended); 1,930 Workspace accounts; 946 GitHub accounts; 1,782 devices; 48,018 audit events.
- `idp_app_assignments`: only 26 rows, all to groups. Only about 25% of active app access is explained by an assignment; Corporate VPN and AWS Console have zero assignments. So "no group path" is a gap, not proof of wrongdoing.
- IdP and Workspace group nesting is only one level deep in practice (still resolved recursively). GitHub teams don't nest; 35 of 51 teams sync from an IdP group. 3 GitHub org owners, 82 current manual org members.
- Workspace accounts link to the IdP only through `person_id` (IDs `gwa_…` vs `idpa_…`). Drive files have owners (an access path with no permission row; 5 owned by archived accounts). No domain or external_email Drive permissions in the data. Some resources have duplicate permission rows to the same group.
- Ended employees with active access: `per_001941` Rowan Mercer, `per_001942` Talia Brooks, `per_001945` Ariel Chen (one of them has Workspace archived but IdP still active). 3 prehires already have active IdP accounts; 103 active people have IdP but no Workspace account.
- Rare audit combinations that look planted: `lifecycle.offboarding.evaluated` (2), `access.exception.approved` (1), HR changes by a human account (3), GitHub `repository_permission` events (2), MDM event with unknown actor on an `ip_address` (1), Workspace `oauth_grant` event (1).

## Next steps

1. Audit tools: `get_audit_events` (by actor, target, type, window, with total count) via `audit_log_repo` and a service.
2. Read-only SQL fallback tool with row cap.
3. Pick and run at least two demo investigations (e.g. offboarding gaps for ended employees; sign-ins after revocation or MFA gaps; the planted rare events), save outputs.
4. README: setup, architecture, how it was tested, limitations, next steps.
5. Tests for repos and services (nested groups, expiry, typed IDs).
6. Regenerate the session transcript and add the earlier session `0db37950` before submitting.
