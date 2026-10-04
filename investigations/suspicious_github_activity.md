# Investigation: suspicious GitHub activity

**Question:** is there anything suspicious in the recent GitHub activity?

```bash
.venv/bin/python entrypoint.py --verbosity mini
```

All results are against the read-only snapshot (`input_data/access_snapshot.sqlite`, snapshot time `2026-08-15T12:00:00Z`). The agent recommends actions but never takes them.

## Example run

Tool calls: `find_change_events` (GitHub, last 30 days) → in one step, `get_activity_timeline` around the two flagged events, `get_person_access` for grantor and grantee, and `find_privileged_access` → draft report → evidence check → final report.

```text
SUMMARY
  Yes. A production-critical repository received a non-expiring admin grant without an approval
  reference, and the recipient weakened branch protection about six hours later.

FINDINGS
  1. Undocumented production admin grant
     Leo Sato granted Devon Shah admin access to production-critical data-pipelines without an approval
     reference or expiry.
     evidence: evt_00048008, ghrp_000141, ghr_000004, gha_000401, gha_001944
  2. Branch protection weakened
     About 6.5 hours after receiving admin, Devon reduced data-pipelines required reviews from two to one.
     evidence: evt_00048009, evt_00048008, ghr_000004, gha_001944
  3. Sequence warrants investigation (inference)
     The rapid privilege grant and control reduction may indicate unauthorized or insufficiently
     reviewed administrative activity.
     evidence: evt_00048008, evt_00048009, ghrp_000141
  4. Grantor holds owner role
     Leo is an active GitHub organization owner, so the grant was made from a highly privileged account.
     evidence: ghom_000186, gha_000401, per_000401
  5. Separate grant was controlled
     A separate write grant to Jordan Kim referenced CHG-28441 and expires August 22.
     evidence: evt_00048010, ghrp_000142, gha_001943

DATA GAPS
  - The records do not include a ticket or business justification for Devon's admin grant or
    branch-protection change.
  - Audit events prove account actions but do not establish which human controlled each account.

RECOMMENDED ACTIONS
  1. Confirm immediately with Leo and Devon whether both actions were authorized.
  2. Restore the two-review branch-protection requirement unless an approved exception exists.
  3. Remove or time-limit Devon's admin grant if it lacks documented need.
  4. Review Devon's subsequent repository actions and authentication context.
  5. Require approval references and expiry for direct privileged repository grants.

Evidence check: 11 IDs checked, 0 not found in draft, revised: yes, findings changed: 2, dropped: 0
```

## What to notice

- The agent separated the one uncontrolled grant from a nearby grant that had a change ticket and expiry (finding 5), instead of flagging every grant in the window.
- The escalation claim (finding 3) is marked as an inference, and the data gaps say the audit log can't prove which human controlled each account.
- The evidence check changed 2 findings after the model re-read the records behind its cited IDs.

## How we checked it

The grant (`evt_00048008`, `ghrp_000141`) and the branch-protection change (`evt_00048009`, `ghr_000004`) were first surfaced by exploratory SQL over recent, rare `audit_events` during development, before `find_change_events` existed, and used as the known answer for this run. `ghrp_000141` has no `approval_reference` and no `expires_at`, and `ghr_000004` is `production_critical`.
