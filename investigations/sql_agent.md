# Investigation: open-ended questions (SQL agent)

**Question:** anything the schema can support, including questions we didn't build a tool for. This is the path for unprepared questions.

```bash
.venv/bin/python entrypoint.py --agent sql --verbosity mini   # mini prints each query as it runs
```

All results are against the read-only snapshot (`input_data/access_snapshot.sqlite`, snapshot time `2026-08-15T12:00:00Z`). The agent recommends actions but never takes them.

## How it works

`SqlAgentService` (`access_agent/sql_agent_service.py`) runs the same loop as the tools agent with different tools:

- `run_sql`: one read-only SELECT per call (100 rows by default, max 500, 10 s timeout). Errors go back to the model so it can fix the query.
- `read_code`: reads this project's Python and `SCHEMA.md`, e.g. to reuse the tested nested-group SQL in `access_agent/repos/`. Only exact paths from a fixed list are readable.
- `submit_report`: the same structured report as the tools agent (summary, findings marked fact or inference with IDs, data gaps, recommended actions).

The prompt preloads `SCHEMA.md` and the table DDL (~25k characters), so the model rarely spends steps discovering the schema. The step limit is 40, compared with 15 for the tools agent.

## Read-only safety

SQLite has no users or grants, so `access_agent/db.py` enforces read-only in layers on the shared connection:

1. The file is opened with `mode=ro`.
2. `PRAGMA query_only = ON` is set.
3. An authorizer denies every statement except reads, blocking writes, DDL, temp tables, PRAGMA, ATTACH, transactions, and VACUUM.
4. A progress handler aborts queries after 10 s.

## Example run: "Find every bad offboarding in this data."

Full prompt: "Find every bad offboarding in this data. Consider people who left whose access was not fully removed in any system (IdP, Workspace, Drive, GitHub, devices, OAuth), activity after leaving, failed or partial offboarding events, access exceptions, and accounts that are still active but not linked to any current person. Be thorough and rank by severity."

28 queries over 8 steps, ~110 s. It wrote its own recursive CTE for nested Workspace groups and Drive permissions, and checked unlinked accounts across all three systems. Every finding below was re-checked by hand against the database.

```text
SUMMARY
  No, offboarding is incomplete. Three leavers retain broad active access and show post-departure activity; 23
  others retain access, 16 had delayed deprovisioning, and one unlinked bot remains privileged.

FINDINGS

  1. Talia retains critical access
     Talia Brooks retains active IdP and GitHub access, seven applications, production-critical repositories,
     and recorded activity 36 days after departure.
     evidence: per_001942, idpa_001942, gha_001942, ghom_000894, ghtrp_000146, ghtrp_000151 +4 more

  2. Rowan remains active everywhere
     Rowan Mercer retains active IdP, Workspace, and GitHub accounts, eight applications, restricted Drive
     data, production repositories, a device, and recent activity.
     evidence: per_001941, idpa_001941, gwa_001941, gha_001941, aua_007681, drvp_000027 +4 more

  3. Ariel offboarding failed
     Ariel Chen retains active accounts, six applications, restricted Drive data, production GitHub access,
     and a device; Workspace archiving failed before subsequent activity.
     evidence: per_001945, idpa_001945, gwa_001945, gha_001945, aua_007704, drvp_000055 +4 more

  4. Unlinked production bot active
     Unlinked legacy-release-bot remains active, recently used, an organization member, and a write
     collaborator on production-critical payments-api.
     evidence: gha_900001, ghom_000946, ghrp_000143

  5. Nine retain direct GitHub grants
     Nine other leavers retain direct GitHub grants: Casey Cohen, Priya Petrov, Hugo Clark, Parker Choi, Kai
     Mercer, Jae Thomas, Mateo Miller, Jonah Anders, and Felix Garcia.
     evidence: ghrp_000137, ghrp_000072, ghrp_000107, ghrp_000084, ghrp_000041, ghrp_000115 +3 more

  6. Fourteen retain other access
     Fourteen additional leavers retain Drive, OAuth, or group access; Luis Kaur also retains a GitHub team
     and IdP assignment.
     evidence: per_000031, per_001395, per_000713, per_000124, per_000279, per_000775 +22 more

  7. Delayed removals and exception
     Sixteen IdP deprovisionings finished one day late; the sole access exception targets active contractor
     Jordan Kim, not a leaver.
     evidence: idpa_001736, idpa_000558, idpa_000899, idpa_000124, idpa_001953, idpa_000279 +12 more

DATA GAPS
  - Audit logs are incomplete, and the snapshot lacks approved-OAuth inventory and ownership records for the
    unlinked service account.

RECOMMENDED ACTIONS
  1. Immediately suspend Talia Brooks, Rowan Mercer, and Ariel Chen across IdP, Workspace, GitHub,
     applications, and devices; preserve logs for investigation.
  2. Revoke all current GitHub, Drive, OAuth, group, assignment, ownership, and device access held by the
     remaining leavers.
  3. Disable or formally assign and approve legacy-release-bot, then rotate its credentials and review recent
     production activity.
  4. Investigate all post-departure activity and the failed or partial lifecycle events, including source IPs,
     affected resources, and human initiators.
  5. Fix lifecycle policy coverage and add controls that verify complete removal across every connected
     system.
```

**What it found that the removal analysis didn't:** the unowned `legacy-release-bot`, which the per-person checks can't see. It also called out the one access exception as unrelated to any leaver. Both are now in `removal_analysis.md`.

**What it missed or got wrong:**
- It didn't mention that the 9 GitHub accounts with leftover grants are suspended, so those grants are dormant, not live access.
- It also didn't note that the 16 "one day late" deprovisionings are mostly a timezone artifact: HR end dates are local, while IdP timestamps are UTC.

## Example run: "Was Ariel Chen offboarded properly?"

About a dozen queries in four steps (people → accounts and groups → Drive, GitHub, and audit events → report), ~28 s.

```text
SUMMARY
  No, Ariel Chen's offboarding is incomplete. Twelve days after employment ended, core accounts and
  critical access remain active, with successful post-departure activity.

FINDINGS

  1. Post-departure activity confirmed
     Ariel's accounts logged in, viewed Drive content, and authenticated to Snowflake after the
     August 3 end date.
     evidence: evt_00048016, evt_00037716, aua_007707, per_001945

  2. Core accounts remain active
     IdP, Workspace, and GitHub accounts remain active; the Workspace archive attempt failed on the
     end date.
     evidence: idpa_001945, gwa_001945, gha_001945, evt_00048015, evt_00048014

  3. Six applications remain active
     Six applications still report active access, including critical VPN, GitHub, Workspace,
     PagerDuty, and Snowflake access.
     evidence: aua_007708, aua_007705, aua_007709, aua_007706, aua_007707, aua_007704

  4. GitHub access persists
     Ariel remains an organization member on two teams with access to six repositories, including
     one production-critical repository.
     evidence: ghom_000897, ghtm_001393, ghtm_001394, ghtrp_000085

  5. Restricted Drive access persists
     Three current Workspace group memberships provide access to eight Drive resources, including
     four restricted shared drives.
     evidence: gwm_002747, gwm_002748, gwm_002900, drvp_000175, drvp_000115

  6. IdP memberships still grant access
     Six current IdP group memberships remain, including nested groups that grant Workspace and
     Snowflake.
     evidence: idpm_009641, idpm_009642, idpm_009644, idpm_009643, idpm_010182, idpm_010243 +2 more

  7. Company device not retired
     Ariel's compliant company Windows device remains enrolled and was not retired after employment
     ended.
     evidence: dev_001945, per_001945

DATA GAPS
  - Audit logs are incomplete, so the records may not show every offboarding attempt or post-
    departure action.

RECOMMENDED ACTIONS
  1. Immediately disable Ariel's IdP and Workspace accounts and suspend GitHub access.
  2. Revoke all six application access records, prioritizing Snowflake and VPN.
  3. Remove IdP, Workspace, GitHub organization, and team memberships.
  4. Retire or recover the company Windows device.
  5. Investigate the failed Workspace archive and the post-departure login, Snowflake
     authentication, and Drive view.
```

## How we checked it

- Compared against the removal analysis for the same person: the SQL agent reached the same conclusions and cited the same IDs without using those checks (see `removal_analysis.md`).
- Read-only guards: tried `DELETE`, `UPDATE`, `INSERT`, `DROP`, `CREATE TEMP TABLE`, `PRAGMA query_only = OFF`, `ATTACH`, `BEGIN`, `VACUUM INTO`, `load_extension`, `pragma_table_info`, a CTE-wrapped `DELETE`, and stacked statements. All were rejected, no files were created, and the database checksum was unchanged. An infinite recursive query was stopped at 10 s.

## Known limitations

- Slower and costlier than the tools agent (~10–30 LLM calls per question).
- Its SQL isn't reviewed before it runs; correctness depends on the model reading the schema guide (e.g. treating a grant as current only when `revoked_at` is null and it hasn't expired).
- Similar names (e.g. Rowan Mercer and Rowan P. Mercer) can cause wrong matches if the model doesn't ask to clarify.

## What we'd build next

- Saved evaluation questions with expected IDs, run against both agents.
- Showing the queries behind each finding in the report, so a reviewer can re-run them.
