# Access Investigation Agent

An LLM agent that investigates employee access across HR, the IdP, Google Workspace, GitHub, devices, and audit logs. It runs over a read-only SQLite snapshot (`input_data/access_snapshot.sqlite`, as of `2026-08-15T12:00:00Z`) and produces reports that cite record IDs, separate facts from inferences, and list data gaps. It recommends actions but never changes data.

Sections: [Setup](#1-setup) · [Scope and architecture](#2-scope-and-architecture) · [Example investigations](#3-example-investigations) · [How I checked it works](#4-how-i-checked-it-works) · [Limitations and next steps](#5-limitations-and-next-steps). Coding-agent transcripts are in `sessions/`.

## 1. Setup

Requires Python 3.12 and an [OpenRouter](https://openrouter.ai) API key.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
export OPENROUTER_API_KEY=sk-or-...        # or put the key in token.txt (gitignored)

.venv/bin/python entrypoint.py                     # tools agent (default)
.venv/bin/python entrypoint.py --agent sql         # SQL agent, for questions the tools don't cover
.venv/bin/python entrypoint.py --verbosity mini    # also print each tool call
```

Startup prints example questions. Optional: `OPENROUTER_MODEL` (default `openai/gpt-5.6-sol`), `ACCESS_DB_PATH`.

## 2. Scope and architecture

**In scope:** who can access what and why, whether offboarding removed access, suspicious audit-log changes, privileged access, risky OAuth grants, MFA gaps, IdP vs. application provisioning, and data-quality issues that would mislead an investigator. **Out of scope:** remediation (no write tools; the DB connection can't write), live connectors, and any UI beyond the CLI.

```text
entrypoint.py                        CLI
  └─ agent_service.py                hand-written tool loop, system prompt + playbooks, evidence check
       └─ tools/                     one file per tool: Pydantic args + description
            └─ services/             investigation logic (cross-system joins, severity, flags)
                 └─ repos/           all SQL, one repo per system
                      └─ db.py       read-only SQLite connection
```

**Tools agent (default).** 14 deterministic, investigation-shaped tools, e.g. `analyze_removal` (what survived one person's offboarding, ranked by severity), `get_leftover_direct_grants`, `find_change_events`, `get_activity_timeline`, `find_privileged_access`, `find_risky_oauth_grants`, `find_mfa_gaps`, `reconcile_app_assignments`, `find_lifecycle_anomalies`, `find_unlinked_accounts`. It finishes by calling `submit_report` with a structured report. About 20–30 s per investigation.

**SQL agent (`--agent sql`).** Gets the schema in its prompt and writes its own read-only SQL. Each run proposes reusable tools (validated by executing them) and is saved to `investigations/runs/`. Several tools above started as these proposals.

Key choices:

- **Tools return conclusions, not rows.** The code handles nested groups, timezone tolerance, and dormant vs. live access, so the model reasons over results that are already correct.
- **Context management.** Outputs lead with counts and return only notable rows (e.g. 19 of 57 flagged repo grants; routine logins are hidden from timelines by default). Playbooks in the prompt map question types to tool chains.
- **Evidence check.** The first `submit_report` is a draft. Every cited ID is looked up and the records are sent back with labels for related records. The model must then remove unsupported or nonexistent IDs, fix contradicted facts, downgrade weak claims to `inference`, and resubmit. The CLI shows what changed.
- **Read-only, enforced in layers.** The file is opened with `mode=ro`, `PRAGMA query_only` is on, an authorizer allows only reads, and queries time out after 10 s.

## 3. Example investigations

Each write-up has the findings, real agent output, and how the result was checked against the data.

- `[removal_analysis.md](investigations/removal_analysis.md)` (tools agent): did offboarding remove access? 3 people kept active critical access and used it after leaving, 22 kept direct grants, and an unowned bot pushes to production. Includes a company-wide run and a single-person run.
- `[suspicious_github_activity.md](investigations/suspicious_github_activity.md)` (tools agent): an unapproved, non-expiring admin grant on a production repo, followed six hours later by the grantee cutting required reviews from 2 to 1.
- `[revoked_relationships.md](investigations/revoked_relationships.md)` (SQL agent): revocation only runs at offboarding, and direct grants are never revoked for anyone.
- `[application_access_gaps.md](investigations/application_access_gaps.md)` (SQL agent): half of IdP-assigned access never shows up in the application.
- `[sql_agent.md](investigations/sql_agent.md)`: how the SQL agent works, with example runs and where it went wrong.

Raw SQL agent runs (question, every query with its purpose, report, proposed tools) are in `investigations/runs/`.

## 4. How I checked it works

All checking was done during development with a coding agent (Cursor); the full sessions are in `sessions/`.

- **Tool outputs against direct SQL.** Services were run outside the agent and their output compared with ad-hoc queries against the snapshot. This caught real bugs:
  - 21 false "critical" offboardings: a UTC day boundary made last-day logins look like post-departure use. Fixed with a 1-day tolerance.
  - Grants on suspended GitHub accounts were reported as live access. They're now flagged as dormant.
  - 195 accounts flagged for "activity before the account existed", which turned out to be a data artifact. The tool now summarizes it and its description warns about it.
- **Write-ups checked against the data.** A recommended fix in an early write-up would have removed a group-nesting row (`idpm_010248`) and cut GitHub access for every external engineer. On review it was corrected to the person's own missed membership (`idpm_006915`).
- **End-to-end runs with known answers.** Before the security tools were built, exploratory SQL (by the coding agent and the SQL agent) surfaced a set of leads. After building the tools, the tools agent was given generic questions ("Has anything suspicious happened in the last two weeks?") and checked for whether it found those leads with the right IDs:
  - Devon Shah's unapproved admin grant and branch-protection change;
  - the unowned bot tied to a device-attribution failure by IP and correlation ID;
  - a single-user third-party app reading a user's Gmail;
  - the 3 failed offboardings.
- **Built-in checks.**
  - The evidence check verifies every cited ID exists; in the two tools-agent runs linked above it revised 5 and 2 findings.
  - SQL agent tool proposals are executed before they're accepted.
  - `--verbosity mini` shows every tool call and its result size, which is how I cut a 73k-character timeline down to 2k.
  - Write attempts (INSERT, DROP, ATTACH) were run against the connection and are rejected.

## 5. Limitations and next steps

**Limitations**

- No automated regression tests; checking was manual and end-to-end.
- The evidence check is the model checking itself. Existence of each cited ID is guaranteed; whether a record supports a claim is judged by the LLM.
- Severity rules and thresholds were tuned on this snapshot.
- The tools agent can't fall back to SQL; the user has to switch agents.
- Session history isn't compacted, so long sessions grow.
- Data limits: audit logs start 2026-02-16 and don't identify humans, and 5 people have impossible HR dates. These are reported as data gaps.

**Next steps**

1. **A non-LLM API over the same services.** The tools are already deterministic code, so expose them directly, e.g. `GET /records/{id}`, `GET /people/{id}/access`, `GET /people/{id}/removal-analysis`, `GET /changes?since=`. Every evidence ID in a report would link to its record, so a reviewer can check any finding without trusting the model.
2. **Validate, then act.** A reviewer confirms or rejects each finding, and confirmed findings become concrete remediation actions (disable this account, revoke this grant). Approved actions run through a separate, permissioned and audited service with a dry run first, and the relevant check is re-run afterwards to confirm the access is gone. The agent proposes; it never executes.
3. **A reconciliation API.** In production, the core service would continuously compare desired state (HR status, then IdP assignments) with actual state in every system, and expose the drift through the API: who should have access but doesn't, who has access but shouldn't, and since when. `reconcile_app_assignments` and `analyze_removal` already do this for one slice. Most findings here (failed offboardings, leftover grants, unprovisioned app access) are reconciliation failures, so the agent would mostly explain and prioritize drift instead of discovering it.
4. An eval set of questions with expected findings and IDs, scored on every change.
5. Live connectors to the IdP, Workspace, and GitHub instead of a snapshot.

