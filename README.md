# Access Investigation Agent

An LLM agent that helps a security team investigate employee access across HR, the identity provider (IdP), Google Workspace, GitHub, devices, and audit logs. It works over a read-only SQLite snapshot (`input_data/access_snapshot.sqlite`, snapshot time `2026-08-15T12:00:00Z`) and answers with reports that cite record and event IDs, separate facts from inferences, and list data gaps. It recommends actions but never changes data.

## Setup

Requires Python 3.12.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Provide an [OpenRouter](https://openrouter.ai) API key, either as an environment variable or in a `token.txt` file at the repo root (gitignored, never committed):

```bash
export OPENROUTER_API_KEY=sk-or-...
# or
echo "sk-or-..." > token.txt
```



## Running

```bash
.venv/bin/python entrypoint.py                              # tools agent (default)
.venv/bin/python entrypoint.py --agent sql                  # SQL agent
.venv/bin/python entrypoint.py --verbosity mini             # also print each tool call
```

Type a question at the `you>` prompt. Quit with `exit`, Ctrl-C, or Ctrl-D. Remaining OpenRouter credit is printed at startup.


| Flag          | Values                                                                      | Default |
| ------------- | --------------------------------------------------------------------------- | ------- |
| `--agent`     | `tools`: purpose-built tools. `sql`: the model writes its own read-only SQL | `tools` |
| `--verbosity` | `clean`: answers only. `mini`: tool-call logs. `verbose`: all logs          | `clean` |


Optional environment variables:


| Variable             | Purpose                             | Default                             |
| -------------------- | ----------------------------------- | ----------------------------------- |
| `OPENROUTER_API_KEY` | API key (falls back to `token.txt`) | —                                   |
| `OPENROUTER_MODEL`   | Any OpenRouter model ID             | `openai/gpt-5.6-sol`                |
| `ACCESS_DB_PATH`     | Path to the SQLite snapshot         | `input_data/access_snapshot.sqlite` |




### Example questions

- "Was Ariel Chen offboarded properly?"
- "Check whether removed people's access was removed properly."
- "Do people who left still hold any direct grants?"
- "Which applications are not provisioning the users the IdP assigns to them?"
- "Which people have records with impossible dates?"
- "Who has access to the payments-api repository, and how?" (SQL agent)

Simple lookups get a plain-text answer. Investigations end in a report with a summary, numbered findings with evidence IDs, data gaps, and recommended actions.

## The two agents

**Tools agent** (`access_agent/agent_service.py`): the model calls purpose-built tools whose logic is deterministic and tested against the data. It's fast (~20 s per investigation) and consistent.


| Tool                                     | What it does                                                                                                                    |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `list_people`, `find_person`             | Browse people; resolve a name or email to a `person_id`                                                                         |
| `get_person_access`                      | Everything a person can access: IdP groups (nested) and apps, Workspace groups and Drive, GitHub org, teams, and repos, devices |
| `list_removed_people`, `analyze_removal` | Who has left, and per-person checks of whether their access was removed, with severity                                          |
| `get_leftover_direct_grants`             | Drive, GitHub collaborator, and OAuth grants still held by people who left                                                      |
| `reconcile_app_assignments`              | IdP assignments compared with what each application reports, with coverage per app                                              |
| `find_hr_date_issues`                    | Records with dates in an impossible order (end before start, etc.)                                                              |
| `submit_report`                          | Final structured report                                                                                                         |


**SQL agent** (`access_agent/sql_agent_service.py`): for questions the tools don't cover. The model gets the schema guide and table definitions in its prompt, writes its own read-only SQL (`run_sql`), and can read this project's code (`read_code`) to reuse tested queries. It's slower and costlier (~10–30 LLM calls per question). Each run also:

- proposes reusable tools generalized from its queries, and validates each one by running it;
- saves the question, every query with its purpose, and the report to `investigations/runs/`.

That is how the last three tools above were built.

## Safety

- **Read-only database:** SQLite has no users or grants, so `access_agent/db.py` enforces read-only in layers. The file is opened with `mode=ro`, `PRAGMA query_only` is on, an authorizer rejects anything other than reads (writes, DDL, PRAGMA, ATTACH, transactions), and queries time out after 10 s.
- **No remediation:** the agent has no tools that change anything. It can only recommend actions.
- **API key:** read from the environment or `token.txt`, which is gitignored.



## Investigations

Write-ups with findings and real agent outputs are in `investigations/`:

- `[removal_analysis.md](investigations/removal_analysis.md)`: bad offboardings. 3 people whose offboarding failed entirely and who kept using their accounts, confidential Drive access months after leaving, dormant repo grants, and an unowned bot pushing to production.
- `[revoked_relationships.md](investigations/revoked_relationships.md)`: what revocation actually removes. Direct grants are never revoked for anyone.
- `[application_access_gaps.md](investigations/application_access_gaps.md)`: IdP assignments compared with application records. Half of assigned access never reaches the app, and 5 HR records have impossible dates.
- `[sql_agent.md](investigations/sql_agent.md)`: how the SQL agent works, with example runs and where it went wrong.



## Project layout

```text
entrypoint.py               interactive CLI
playground_entrypoint.py    quick manual checks: no args (sample repo rows), `llm <prompt>`, `person <name>`
access_agent/
  db.py                     read-only SQLite connection
  llm_client.py             OpenRouter client (OpenAI-compatible API)
  agent_service.py          tool-calling loop and system prompt
  sql_agent_service.py      SQL agent: prompt, tool proposals, run saving
  models/                   Pydantic models for records, reports, and proposed tools
  repos/                    all SQL, one repo per system
  services/                 investigation logic (person access, removal analysis, access review)
  tools/                    one file per tool, plus registry.py
investigations/             investigation write-ups and saved SQL agent runs
docs/idp_connections.html   diagrams of how the tables connect
sessions/                   coding-agent session transcripts
input_data/                 the snapshot and SCHEMA.md
```

