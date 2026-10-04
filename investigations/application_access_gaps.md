# Investigation: application access gaps

**Question:** do the IdP's application assignments match what the applications report, and is anything missing?

Source run: SQL agent, `investigations/runs/20261004_154800_okay_please_look_into_all_relationships_that_have_.json` (18 queries, no errors). The revoked-relationships half is in `revoked_relationships.md`. Every number below was re-checked by hand against the snapshot (`2026-08-15T12:00:00Z`), and two of the agent's findings were reinterpreted (see "What the agent got wrong").

## Background

Per `SCHEMA.md`, two tables describe application access from different sides:

- `idp_app_assignments`: what the IdP is configured to grant (26 assignments, all to groups, granted to accounts directly or through nested groups).
- `application_user_access`: what each application reports for each IdP account.

If the IdP grants an app to a group, every account in that group should have an application access row for that app.

## Findings

### 1. Half of IdP-assigned access never shows up in the application

Current assignments add up to 3,792 account–application pairs. Only 1,898 have an application access row; **1,894 have no row at all**. All 1,894 accounts are active in the IdP, and almost all belong to active workers (1,862 active, 29 on leave, 2 ended, 1 prehire).

The gap depends entirely on the application:

| Application | Assignments | Expected | Present | Coverage |
| --- | --- | --- | --- | --- |
| Google Workspace | `idpaa_000001`, `_007`, `_013`, `_019`, `_025` | 723 | 723 | 100% |
| GitHub (bundles) | `idpaa_000006`, `_012`, `_018`, `_024` | 568 | 261 | 46% |
| Snowflake | `idpaa_000003`, `_009`, `_015`, `_021` | 660 | 306 | 46% |
| Figma | `idpaa_000005`, `_011`, `_017`, `_023` | 615 | 239 | 39% |
| PagerDuty | `idpaa_000004`, `_010`, `_016`, `_022` | 611 | 239 | 39% |
| Salesforce | `idpaa_000002`, `_008`, `_014`, `_020` | 571 | 92 | **16%** |
| GitHub (`github-production-contributors`) | `idpaa_000026` | 44 | 38 | 86% |

**Inference:** this is systematic, not random. Google Workspace is fully provisioned, while Salesforce has received only about one in six assigned users. Most likely the SCIM sync to the other apps is broken or partial, or those apps only create users on first sign-in. The data can't tell these apart. Either way, the IdP's view of who has access is not what the applications enforce. For people who left, a missing row is harmless. For active people, it means access reviews based on IdP assignments will be wrong in both directions.

### 2. Five people who left have impossible dates

22 application access rows were revoked before they were assigned. They all belong to 5 people whose HR `end_date` is before their `start_date`, and whose IdP account was deactivated before it was created:

| Person | Start | End | IdP account |
| --- | --- | --- | --- |
| Camila Campbell (`per_001209`) | 2026-06-24 | 2025-10-23 | `idpa_001209`, 7 rows |
| Elena Lopez (`per_002015`) | 2026-05-11 | 2025-12-21 | `idpa_002015`, 6 rows |
| Kai Brooks (`per_000062`) | 2026-03-08 | 2025-10-30 | `idpa_000062`, 3 rows (e.g. `aua_000245`) |
| Fatima Rivera (`per_000434`) | 2025-11-19 | 2025-11-13 | `idpa_000434`, 3 rows |
| Quinn Rossi (`per_001023`) | 2026-05-25 | 2026-01-19 | `idpa_001023`, 3 rows |

**Inference:** these look like rehires whose old end date was never cleared, or start and end dates swapped on import. In either case, HR marks them as ended. If they are actually rehired and working, their access was revoked by mistake. If they did leave, the start dates are wrong. Either way, their HR record needs checking. Any tool that computes "days since leaving" will give wrong answers for them.

### 3. A missed group membership still grants GitHub to someone who left

Luis Kaur (`per_001395`, left 2026-07-03) has revoked GitHub access (`aua_005519`) and a deprovisioned IdP account. Offboarding missed his `external-engineering` membership (`idpm_006915`), and that group is nested into `github-production-contributors` (`idpm_010248`), whose assignment `idpaa_000026` grants GitHub. This is one of the 3 non-active rows in the reconciliation. The IdP still says he should have GitHub, while the app correctly says revoked. Details in `revoked_relationships.md`.

### 4. Most app access isn't explained by any assignment, by design

7,441 application rows are active and SCIM-provisioned, and 5,647 of them have no matching assignment. This is expected rather than a gap: Corporate VPN (1,865 rows) and AWS Console (241) have no assignments at all, and only 26 assignments exist in total. Assignments are a partial export of how access was granted, not a complete source of truth. Treat "no assignment" as "unexplained", not "unauthorized".

## What the agent got wrong

- **Unassigned SCIM rows:** it reported the 5,647 active SCIM rows without an assignment as a major reconciliation gap. They mostly come from apps that have no assignments at all (finding 4).
- **Prehire access:** it flagged two prehires' suspended access (`aua_004107` for Priya Miller, `aua_006161` for Mateo Thompson) as conflicts. Both rows have an `assigned_at` after the snapshot, matching their future start dates, so this is access staged ahead of their first day.
- **Date errors:** it reported the 22 bad timestamps as an application data problem. They trace back to 5 bad HR records (finding 2).

## Data gaps

- The data can't tell broken SCIM sync apart from apps that only create users on first sign-in, since there are no provisioning attempt or failure events for these apps.
- Assignments are a partial export, so we can't say whether unexplained access was granted manually, by an older assignment, or not at all.

## Recommended actions

1. Check SCIM provisioning for Salesforce first (16% coverage), then Figma, PagerDuty, Snowflake, and GitHub, against Google Workspace's 100%.
2. Have HR review the 5 people with an end date before their start date, and confirm whether they were rehired.
3. Remove Luis Kaur's `external-engineering` membership (`idpm_006915`). Don't remove the group nesting `idpm_010248`, which other external engineers rely on.
4. Don't use IdP assignments alone for access reviews until the coverage gap is understood; use `application_user_access` for what's enforced.

## Tools to build from this run

The SQL agent proposed four tools. All ran successfully with their example arguments:

| Proposed tool | Validation | Verdict |
| --- | --- | --- |
| `reconcile_idp_assignments_to_app_access(snapshot_at)` | 500+ rows | **Build.** Correct nested-group logic. Add an `application_id` filter and a per-application summary mode, since the raw output is 1,897 rows. |
| `find_invalid_application_access_timestamps(snapshot_at)` | 22 rows | **Build, broadened.** Generalize to an HR data-quality check (end before start, account deactivated before created), since that's the real cause. |
| `find_active_scim_without_assignment(snapshot_at)` | 500+ rows | **Skip.** Mostly noise, because assignments are a partial export. |
| `list_revoked_relationships(snapshot_at)` | 500+ rows | See `revoked_relationships.md`. |
