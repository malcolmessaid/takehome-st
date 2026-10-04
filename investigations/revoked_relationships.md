# Investigation: revoked relationships

**Question:** what does revocation actually remove in this company, and is anything left behind?

Source run: SQL agent, `investigations/runs/20261004_154800_okay_please_look_into_all_relationships_that_have_.json` (prompt: "look into all relationships that have been revoked, and then look at the application user access and check to see if there are any missing pieces there"). The application-access half is in `application_access_gaps.md`. Every number below was re-checked by hand against the snapshot (`2026-08-15T12:00:00Z`).

## Findings

### 1. Revocation only happens during offboarding, and only for group memberships and app access

Every revoked relationship in the snapshot belongs to one of the 66 people who left and whose IdP account was deprovisioned. Nothing is ever revoked for active people (no role changes, no team moves).

| Relationship | Revoked rows | Accounts | Date range |
| --- | --- | --- | --- |
| `idp_group_memberships` | 264 | 66 | 2025-10-23 to 2026-08-06 |
| `application_user_access` | 263 | 66 | 2025-10-23 to 2026-08-06 |
| `workspace_group_memberships` | 94 | 63 | 2025-10-23 to 2026-08-06 |
| `github_team_memberships` | 47 | 31 | 2025-10-23 to 2026-08-03 |
| `github_org_memberships` | 31 | 31 | 2025-10-23 to 2026-08-03 |
| `drive_permissions` | **0** | — | — |
| `github_repo_collaborators` | **0** | — | — |
| `workspace_oauth_grants` | **0** | — | — |
| `github_team_repo_permissions`, `idp_app_assignments` | 0 | — | — |

### 2. Direct grants are never revoked, which is why people who left still hold them

Offboarding removes group memberships and application access, but there is no record of any direct Drive permission, GitHub collaborator grant, or OAuth grant ever being revoked, for anyone. This is the root cause behind most of the leftover access in `removal_analysis.md`:

- 5 people who left months ago still have a direct grant on a confidential Drive file (e.g. Sam Nguyen, `drvp_000120`, 289 days after leaving).
- 10 suspended GitHub accounts of people who left still have direct repo grants (e.g. Casey Cohen, `ghrp_000137`, write on production-critical `security-automations`).
- People who left still have active OAuth grants to third-party apps.

**Inference:** the deprovisioning process walks group memberships and SCIM-managed app access, but has no step for direct grants. Fixing the process, not just the individual grants, is the real remediation.

### 3. Where revocation did run, it was complete

All 66 deprovisioned accounts had every application access row revoked: none left open (`aua_006625`, `aua_006626` are examples). The rows are also internally consistent: no row is marked `revoked` without a `revoked_at`, and no row has a `revoked_at` but a different status.

The 3 people who left but were never deprovisioned (Rowan Mercer, Talia Brooks, Ariel Chen) have no revoked rows at all. Their offboarding never started, rather than starting and missing things (see `removal_analysis.md`).

### 4. One gap: a missed group membership still grants GitHub to someone who left

Luis Kaur (`per_001395`) left on 2026-07-03. His IdP account is deprovisioned and his GitHub application access is revoked (`aua_005519`). Offboarding revoked 3 of his 4 group memberships on his last day (`idpm_006912`, `idpm_006913`, `idpm_006914`), but missed `external-engineering` (`idpm_006915`). That group is itself a member of `github-production-contributors` (`idpm_010248`), whose assignment `idpaa_000026` grants GitHub. If his account were reactivated, the IdP would push GitHub access back.

**Inference:** `external-engineering` may be skipped because it's managed separately from department, location, and project groups. Other external workers who leave may have the same leftover membership.

## Data gaps

- The audit log has no revocation or deprovisioning event types, so the snapshot shows that a relationship was revoked but not who or what revoked it.
- With no revocations for active people, we can't tell whether role changes are handled at all, or just weren't captured in this snapshot.

## Recommended actions

1. Add direct grants (Drive permissions, GitHub collaborator grants, OAuth grants) to the offboarding process, then sweep existing leftovers for people who left.
2. Remove Luis Kaur's `external-engineering` membership (`idpm_006915`), not the group nesting `idpm_010248`, which would cut GitHub for every external engineer. Then check why deprovisioning skipped that group.
3. Log revocation events so future investigations can tell how and when access was removed.

## Tools to build from this run

The SQL agent proposed `list_revoked_relationships(snapshot_at)` (validated: 500+ rows). It's useful as-is for findings 1 and 3. Finding 2 needs a different tool that the run did not propose: **leftover direct grants for people who left**, covering Drive permissions, collaborator grants, and OAuth grants for people with `employment_status = 'ended'`.
