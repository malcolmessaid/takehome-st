# Investigation: removal analysis

**Question:** for everyone who has left the company, was their access removed properly?

Run it with the tools agent and ask, for example, "Check whether removed people's access was removed properly" or "Was Talia Brooks offboarded properly?":

```bash
.venv/bin/python entrypoint.py --verbosity mini
```

All results are against the read-only snapshot (`input_data/access_snapshot.sqlite`, snapshot time `2026-08-15T12:00:00Z`). The agent recommends actions but never takes them.

## Bad offboardings

Of the 69 people who have left, 3 were not offboarded at all in practice, 5 still have confidential Drive access months later, and 10 have leftover repo grants on suspended GitHub accounts. Separately, an active bot account with no owner still pushes to production. The removal analysis missed it, and the SQL agent found it (see `sql_agent.md`).

### Critical: offboarding failed, and the accounts were used after the person left

| Person | Left | What went wrong | Still has | Used after leaving |
| --- | --- | --- | --- | --- |
| Rowan Mercer (`per_001941`), contractor | 2026-07-25, 21 days before snapshot | HR ended the contract (`evt_00048001`), but the IdP found no deactivation policy for contractors and stopped at "manual review required" (`evt_00048002`) | Active IdP, Workspace, and GitHub accounts (`idpa_001941`, `gwa_001941`, `gha_001941`); AWS Console, VPN, and GitHub app access (`aua_007681`, `aua_007686`, `aua_007683`); member of `github-production-contributors`; 7 repos including production-critical `identity-service`; 4 restricted Sales Drive files | Repo fetches and Drive views up to 20 days after leaving (`evt_00048004`, `evt_00018627`, `evt_00014550`, `evt_00023825`); laptop checked in 8 days after (`dev_001941`) |
| Talia Brooks (`per_001942`), contractor | 2026-07-08, 38 days before snapshot | Same gap: contract ended (`evt_00048005`), IdP stopped at "manual review required" (`evt_00048006`). Her Workspace account was archived and her laptop retired | Active IdP and GitHub accounts (`idpa_001942`, `gha_001942`); VPN, GitHub, and Snowflake access; write access to production-critical `customer-portal` and `payments-api` (`ghtrp_000146`, `ghtrp_000151`) | 8 events up to 36 days after leaving, including repository pushes and pull-request reviews (`evt_00048007`, `evt_00011532`, `evt_00015919`, `evt_00031434`) |
| Ariel Chen (`per_001945`), employee | 2026-08-03, 12 days before snapshot | HR ended employment (`evt_00048014`), but archiving the Workspace account failed after 3 retries with an upstream timeout (`evt_00048015`), and nothing else was removed | Active IdP, Workspace, and GitHub accounts (`idpa_001945`, `gwa_001945`, `gha_001945`); VPN, GitHub, and Snowflake access; 6 repos; 8 Drive files; laptop not retired (`dev_001945`) | A login and a Drive view up to 11 days after leaving (`evt_00048016`, `evt_00037716`); Snowflake used 12 days after (`aua_007707`) |

The pattern: two of the three are contractors, and the IdP has no deactivation policy for contractors, so their offboarding silently stopped at manual review. The third is a failed Workspace archive that was never retried. In all three cases, one failed step meant nothing downstream was removed.

### Critical: active bot account with no owner, pushing to production

`legacy-release-bot` (`gha_900001`) is an active GitHub account that isn't linked to any person, so the per-person removal analysis never looks at it. It was added manually in 2023 as an org member (`ghom_000946`), with direct write access to production-critical `payments-api` (`ghrp_000143`, approval `CHG-11982`, no expiry). It is still in use: 15 audit events, most recently a push to `payments-api` the day before the snapshot (`evt_00048017`), plus earlier pushes to production-critical `billing-jobs` (`evt_00021224`). Nobody in the data owns it, so nobody would offboard it if its creator left.

### High: confidential Drive access months after leaving

All of these accounts were otherwise removed correctly; one Drive permission was missed each time. None of them has any HR termination or offboarding event in the audit log.

| Person | Left | Still has |
| --- | --- | --- |
| Priya Petrov (`per_001550`) | 2026-04-22 (115 days) | Engineering Resource 041, confidential (`drvp_000280`), plus a dormant repo grant (below) |
| Talia Hall (`per_000775`) | 2026-04-12 (125 days) | Engineering Resource 021, confidential (`drvp_000140`) |
| Noor Ahmed (`per_001147`) | 2026-03-29 (139 days) | Engineering Resource 141, confidential (`drvp_000260`) |
| Mina Flores (`per_000744`) | 2026-03-13 (155 days) | Engineering Resource 001, confidential (`drvp_000240`) |
| Sam Nguyen (`per_000372`) | 2025-10-30 (289 days) | Engineering Resource 121, confidential (`drvp_000120`) |

### Worth cleaning up: repo grants on suspended GitHub accounts

Suspending a GitHub account doesn't revoke its direct collaborator grants. These accounts are suspended, so the grants can't be used today, but they come back if the account is ever reactivated. Two are on production-critical repos.

| Person | Left | Leftover grant |
| --- | --- | --- |
| Casey Cohen (`per_000682`) | 2026-07-10 | write on production-critical `security-automations` (`ghrp_000137`) |
| Luis Kaur (`per_001395`), contractor | 2026-07-03 | write on production-critical `payments-api` through a team, plus leftover groups, an owned Drive file, and an OAuth grant |
| Priya Petrov (`per_001550`) | 2026-04-22 | write on `payments-api-73` (`ghrp_000072`) |
| Hugo Clark (`per_001240`) | 2026-03-10 | write on `mobile-app-38` (`ghrp_000107`) |
| Parker Choi (`per_000093`) | 2026-02-19 | write on sensitive `infra-live-45` (`ghrp_000084`) |
| Kai Mercer (`per_002046`) | 2025-12-26 | write on `security-automations-72` (`ghrp_000041`) |
| Jae Thomas (`per_001643`) | 2025-12-12 | maintain on `mobile-app-46` (`ghrp_000115`) |
| Mateo Miller (`per_000341`) | 2025-12-11 | write on sensitive `security-automations-40` (`ghrp_000089`) |
| Jonah Anders (`per_000589`) | 2025-11-28 | write on sensitive `customer-portal-35` (`ghrp_000094`) |
| Felix Garcia (`per_001891`) | 2025-10-23 | maintain on `payments-api-41` (`ghrp_000120`) |

### Not an offboarding issue: the one access exception

The only `access.exception.approved` event (`evt_00048011`) covers Jordan Kim (`per_001943`), an active contractor. It was approved by Iris Flores under `CHG-28441` for "release migration support" and expires 2026-08-22. No leaver has an approved exception, so none of the leftover access above is explained by one.

### All 69 people by highest severity

Computed in 0.04 s total.

| Highest severity | People |
| --- | --- |
| Critical | 3 (above) |
| High | 5 (above) |
| Medium | 18: mostly leftover OAuth grants, owned files, or dormant GitHub grants |
| Low | 11: access removed, but a day or more late |
| Clean | 32 |

## How it works

**Who is checked:** people with `employment_status = 'ended'`, plus anyone whose `end_date` has passed but who isn't marked ended (none in this snapshot).

`RemovalAnalysisService.analyze_person(person_id)` (`access_agent/services/removal_analysis_service.py`) builds the person's full current access (nested groups resolved, revoked and expired grants excluded) and runs deterministic checks. The model gets the checks back through the `analyze_removal` tool and writes the report; it does not decide what counts as a failure. `list_removed_people` lists who to check.

Leftover access is flagged no matter how old it is, but each failure is tagged `recent` (≤ 7 days after end date) or `long_standing`.

| System | Check | Severity when it fails |
| --- | --- | --- |
| IdP | Account still active / suspended / deprovisioned late | high / low / low |
| IdP | Applications still report active access | critical if any app is critical, else medium |
| IdP | Application access revoked after end date | low |
| IdP | Still in groups; groups still grant apps via assignments | medium |
| Workspace | Account still active | high |
| Workspace | Still in groups; still owns Drive files; OAuth grants still active | medium |
| Workspace | Current Drive permissions | high if confidential/restricted, else medium |
| GitHub | Still an org member | critical if owner, else high |
| GitHub | Still on teams | medium |
| GitHub | Repository access | critical if production-critical (medium if the account is suspended, since the grant is dormant) |
| Devices | Not retired; checked in after end date | medium; high |
| Audit | Activity or last login more than 1 day after end date | critical |
| Audit | Activity or last login the UTC day after end date | low (may still be the last local working day) |
| Audit | Offboarding trail: HR termination, `lifecycle.offboarding.evaluated`, `*.failed`, `access.exception.*` | context only |

## Example run: "Check whether Talia Brooks was offboarded properly."

Tool calls: `find_person` → `analyze_removal(per_001942)` → `submit_report`.

```text
SUMMARY
  Talia Brooks was not offboarded properly. Although HR ended her contractor engagement on 2026-07-08
  and her Workspace account and Linux device were handled, 11 checks still fail 38 days later,
  including active IdP and GitHub accounts, critical application and repository access, and
  post-termination activity.

FINDINGS
  [fact] HR records Talia Brooks as an ended Engineering contractor with an end date of 2026-07-08.
      evidence: per_001942, evt_00048005
  [fact] The automated IdP offboarding evaluation required manual review because no deactivation
      policy matched this contractor; the IdP account remains active 38 days after her end date.
      evidence: evt_00048006, idpa_001942
  [fact] Her active GitHub account remains an organization member, belongs to two teams, and retains
      access to five repositories, including write access to the production-critical customer-portal
      and payments-api repositories.
      evidence: gha_001942, ghom_000894, ghtm_001388, ghtm_001387, ghtrp_000046, ghtrp_000146, ...
  [fact] Eight audit events are attributed to her accounts more than one day after termination,
      including logins, application authentication, repository fetch/push, and pull-request review;
      the latest occurred 36 days after the end date.
      evidence: evt_00048007, evt_00011532, evt_00015919, evt_00031434, evt_00025376, ...
  [inference] The post-termination activity combined with persistent critical access represents an
      active security exposure. Audit attribution proves activity by associated accounts but does not
      establish which human operated them.
      evidence: idpa_001942, gha_001942, ghom_000894, evt_00048007, ...
  [fact] Two controls did complete successfully: the Workspace account is archived and the assigned
      Linux device is retired.
      evidence: gwa_001942, dev_001942
  (abridged)

DATA GAPS
  - Audit logs are incomplete, so the listed events may not represent all post-termination activity.
  - The snapshot does not show whether any temporary post-termination access exception was approved.

RECOMMENDED ACTIONS
  - Immediately disable the IdP account and revoke all active application sessions and assignments.
  - Suspend or remove the GitHub account from the organization, teams, and repositories; rotate
    secrets that may have been exposed through production-critical repositories.
  - Investigate the eight post-termination events, especially repository pushes.
  - Correct the contractor offboarding policy gap that produced the manual-review condition.
  (abridged)
```

(This run used the earlier report format. The current format adds a short title to each finding and caps evidence display at 6 IDs.)

## How we checked it

- Ran `analyze_person` on all 69 people and read the flagged cases. The first run flagged 21 people as critical; most were false positives where the IdP `last_login_at` equals `deactivated_at` on the UTC day after a local end date. Adding a 1-day timezone tolerance moved those to low.
- Casey Cohen and Luis Kaur have production-repo grants on suspended GitHub accounts; these were downgraded to medium with an explanation rather than reported as critical.
- The SQL agent, which doesn't use these checks, reached the same conclusions and IDs for Ariel Chen. Asked to find every bad offboarding, it confirmed the same 3 critical people and the leftover grants, and found the unowned bot account the checks miss (see `sql_agent.md`).

## Known limitations

- Only covers people HR marks as ended or with a past end date; it can't find people who left but whose HR record was never updated.
- Works one person at a time, so accounts not linked to any person (like `legacy-release-bot`) are never checked.
- Severity rules are hand-picked for this snapshot and not tuned against real incidents.
- Audit logs are incomplete, so "no activity after end date" is not proof of no activity.
- Duplicate Drive permission rows can inflate counts.

## What we'd build next

- `analyze_all`: run the analysis for everyone at once and rank the results (already fast enough at 0.04 s for all 69).
- An unowned-accounts check: active accounts in any system with no linked person, especially ones with privileged or production access.
- Saved evaluation cases with expected IDs, so changes to prompts or checks can be regression-tested.
