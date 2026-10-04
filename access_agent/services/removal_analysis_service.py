from datetime import date, timedelta

from access_agent.logger import get_logger
from access_agent.models.people import Person
from access_agent.models.person_access import PersonAccess
from access_agent.models.removal_analysis import SEVERITY_ORDER, Age, CheckStatus, RemovalAnalysis, RemovalCheck, Severity
from access_agent.repos.audit_log_repo import AuditLogRepo
from access_agent.repos.google_workspace_repo import GoogleWorkspaceRepo
from access_agent.repos.people_repo import PeopleRepo
from access_agent.services.person_access_service import PersonAccessService

logger = get_logger(__name__)

RECENT_DAYS = 7
TIMEZONE_TOLERANCE_DAYS = 1  # HR end_date is a local date while timestamps are UTC, so the next UTC day can still be the last working day
SENSITIVE_DRIVE_CLASSIFICATIONS = {"confidential", "restricted"}


def _days_between(start: date | None, timestamp: str | None) -> int | None:
    return (date.fromisoformat(timestamp[:10]) - start).days if start and timestamp else None


def _age(days: int | None) -> Age | None:
    return None if days is None else Age.RECENT if days <= RECENT_DAYS else Age.LONG_STANDING


def _fail(system: str, check: str, severity: Severity, detail: str, days: int | None, evidence_ids: list[str]) -> RemovalCheck:
    return RemovalCheck(system=system, check=check, status=CheckStatus.FAIL, severity=severity, detail=detail, days_after_end=days, age=_age(days), evidence_ids=evidence_ids)


def _ok(system: str, check: str, detail: str, evidence_ids: list[str], status: CheckStatus = CheckStatus.PASS) -> RemovalCheck:
    return RemovalCheck(system=system, check=check, status=status, severity=Severity.INFO, detail=detail, days_after_end=None, age=None, evidence_ids=evidence_ids)


class RemovalAnalysisService:
    """Checks whether people who left the company actually lost their access."""

    def __init__(self):
        self.people_repo = PeopleRepo()
        self.workspace_repo = GoogleWorkspaceRepo()
        self.audit_repo = AuditLogRepo()
        self.person_access_service = PersonAccessService()

    def list_removed_people(self, since_days: int | None = None) -> list[Person]:
        snapshot_date = self.people_repo.get_snapshot_time()[:10]
        since_date = (date.fromisoformat(snapshot_date) - timedelta(days=since_days)).isoformat() if since_days is not None else None
        logger.info(f"Listing removed people since_days={since_days} since_date={since_date}")
        return self.people_repo.list_removed_people(snapshot_date, since_date)

    def analyze_person(self, person_id: str) -> RemovalAnalysis | None:
        logger.info(f"Analyzing removal person_id={person_id}")
        access = self.person_access_service.get_person_access(person_id)
        if access is None:
            return None
        person = access.person
        end = date.fromisoformat(person.end_date) if person.end_date else None
        days_since_end = _days_between(end, access.snapshot_at)
        checks = [
            *self._idp_checks(access, end, days_since_end),
            *self._workspace_checks(access, days_since_end),
            *self._github_checks(access, days_since_end),
            *self._device_checks(access, end, days_since_end),
            *self._activity_checks(access, end),
            *self._lifecycle_checks(access),
        ]
        failed = [c for c in checks if c.status == CheckStatus.FAIL]
        return RemovalAnalysis(
            person_id=person.person_id,
            full_name=person.full_name,
            worker_type=person.worker_type,
            employment_status=person.employment_status,
            end_date=person.end_date,
            snapshot_at=access.snapshot_at,
            days_since_end=days_since_end,
            highest_severity=min((c.severity for c in failed), key=SEVERITY_ORDER.index, default=Severity.INFO),
            failed_checks=len(failed),
            checks=checks,
        )

    def _idp_checks(self, access: PersonAccess, end: date | None, days_since_end: int | None) -> list[RemovalCheck]:
        if not access.idp:
            return [_ok("idp", "idp_account", "No IdP account is linked to this person.", [], CheckStatus.INFO)]
        checks = []
        for idp in access.idp:
            account = idp.account
            if account.status == "active":
                checks.append(_fail("idp", "idp_account_disabled", Severity.HIGH, f"IdP account {account.username} is still active.", days_since_end, [account.account_id]))
            elif account.status == "suspended":
                checks.append(_fail("idp", "idp_account_disabled", Severity.LOW, "IdP account is suspended but not deprovisioned.", days_since_end, [account.account_id]))
            else:
                lag = _days_between(end, account.deactivated_at)
                if lag is not None and lag > 0:
                    checks.append(_fail("idp", "idp_account_removed_on_time", Severity.LOW, f"IdP account was deprovisioned {lag} days after end_date.", lag, [account.account_id]))
                else:
                    checks.append(_ok("idp", "idp_account_disabled", "IdP account is deprovisioned.", [account.account_id]))

            active_apps = [a for a in idp.app_access if a["status"] == "active"]
            if active_apps:
                critical = any(a["sensitivity"] == "critical" for a in active_apps)
                apps = ", ".join(f"{a['application_name']} ({a['sensitivity']}, {a['provisioning_source']})" for a in active_apps)
                checks.append(_fail("idp", "app_access_revoked", Severity.CRITICAL if critical else Severity.MEDIUM, f"Applications still report active access: {apps}.", days_since_end, [a["access_id"] for a in active_apps]))
            late_apps = [(a, _days_between(end, a["revoked_at"])) for a in idp.app_access if a["status"] == "revoked"]
            late_apps = [(a, lag) for a, lag in late_apps if lag is not None and lag > 0]
            if late_apps:
                worst = max(lag for _, lag in late_apps)
                checks.append(_fail("idp", "app_access_removed_on_time", Severity.LOW, f"{len(late_apps)} application access rows were revoked after end_date, up to {worst} days late.", worst, [a["access_id"] for a, _ in late_apps]))
            if not active_apps and not late_apps and idp.app_access:
                checks.append(_ok("idp", "app_access_revoked", "All application access rows are revoked.", [a["access_id"] for a in idp.app_access]))

            if idp.group_memberships:
                groups = ", ".join(g["group_name"] for g in idp.group_memberships)
                checks.append(_fail("idp", "idp_groups_removed", Severity.MEDIUM, f"Still a current member of {len(idp.group_memberships)} IdP groups: {groups}.", days_since_end, [g["membership_id"] for g in idp.group_memberships]))
            if idp.assigned_but_not_reported:
                apps = ", ".join(x["application_name"] for x in idp.assigned_but_not_reported)
                checks.append(_fail("idp", "idp_assignments_removed", Severity.MEDIUM, f"IdP still grants these apps through current groups: {apps}.", days_since_end, [x["assignment_id"] for x in idp.assigned_but_not_reported]))
        return checks

    def _workspace_checks(self, access: PersonAccess, days_since_end: int | None) -> list[RemovalCheck]:
        if not access.workspace:
            return [_ok("workspace", "workspace_account", "No Google Workspace account is linked to this person.", [], CheckStatus.INFO)]
        checks = []
        for ws in access.workspace:
            account = ws.account
            if account.status == "active":
                checks.append(_fail("workspace", "workspace_account_disabled", Severity.HIGH, f"Workspace account {account.primary_email} is still active.", days_since_end, [account.account_id]))
            else:
                checks.append(_ok("workspace", "workspace_account_disabled", f"Workspace account is {account.status}.", [account.account_id]))
            if ws.group_memberships:
                checks.append(_fail("workspace", "workspace_groups_removed", Severity.MEDIUM, f"Still a current member of {len(ws.group_memberships)} Workspace groups.", days_since_end, [g["membership_id"] for g in ws.group_memberships]))
            if ws.drive_permissions:
                sensitive = [p for p in ws.drive_permissions if p["classification"] in SENSITIVE_DRIVE_CLASSIFICATIONS]
                resources = sorted({f"{p['resource_name']} ({p['classification']})" for p in ws.drive_permissions})
                checks.append(_fail("workspace", "drive_access_removed", Severity.HIGH if sensitive else Severity.MEDIUM, f"Current Drive access to {len(resources)} resources: {', '.join(resources)}.", days_since_end, [p["permission_id"] for p in ws.drive_permissions]))
            if ws.owned_resources:
                checks.append(_fail("workspace", "drive_ownership_transferred", Severity.MEDIUM, f"Still owns {len(ws.owned_resources)} Drive resources; ownership gives access without a permission row.", days_since_end, [r["resource_id"] for r in ws.owned_resources]))
            grants = self.workspace_repo.get_current_oauth_grants(account.account_id)
            if grants:
                apps = ", ".join(g["application_name"] for g in grants)
                checks.append(_fail("workspace", "oauth_grants_revoked", Severity.MEDIUM, f"Third-party apps still authorized: {apps}.", days_since_end, [g["grant_id"] for g in grants]))
        return checks

    def _github_checks(self, access: PersonAccess, days_since_end: int | None) -> list[RemovalCheck]:
        if not access.github:
            return [_ok("github", "github_account", "No GitHub account is linked to this person.", [], CheckStatus.INFO)]
        checks = []
        for gh in access.github:
            account = gh.account
            if gh.org_memberships:
                owner = any(m["org_role"] == "owner" for m in gh.org_memberships)
                sources = ", ".join(m["source"] for m in gh.org_memberships)
                checks.append(_fail("github", "github_org_removed", Severity.CRITICAL if owner else Severity.HIGH, f"GitHub account {account.login} ({account.status}) is still an org {'owner' if owner else 'member'} (source: {sources}).", days_since_end, [account.account_id, *[m["membership_id"] for m in gh.org_memberships]]))
            else:
                checks.append(_ok("github", "github_org_removed", f"GitHub account {account.login} has no current org membership.", [account.account_id]))
            if gh.team_memberships:
                teams = ", ".join(t["team_name"] for t in gh.team_memberships)
                checks.append(_fail("github", "github_teams_removed", Severity.MEDIUM, f"Still on {len(gh.team_memberships)} teams: {teams}.", days_since_end, [t["membership_id"] for t in gh.team_memberships]))
            repo_access = gh.team_repo_access + gh.collaborator_access
            if repo_access:
                critical = [r for r in repo_access if r["sensitivity"] == "production_critical"]
                repos = sorted({f"{r['repository_name']} ({r['permission']}, {r['sensitivity']})" for r in repo_access})
                severity, note = (Severity.MEDIUM, " The GitHub account is suspended, so these grants are dormant until it is reactivated.") if account.status == "suspended" else (Severity.CRITICAL if critical else Severity.MEDIUM, "")
                checks.append(_fail("github", "repo_access_removed", severity, f"Current access to {len(repos)} repositories: {', '.join(repos)}.{note}", days_since_end, [account.account_id, *[r["permission_id"] for r in repo_access]]))
        return checks

    def _device_checks(self, access: PersonAccess, end: date | None, days_since_end: int | None) -> list[RemovalCheck]:
        checks = []
        for device in access.devices:
            if device.retired_at:
                checks.append(_ok("mdm", "device_retired", f"{device.platform} device retired.", [device.device_id]))
                continue
            check_in_lag = _days_between(end, device.last_check_in_at)
            if check_in_lag is not None and check_in_lag > 0:
                checks.append(_fail("mdm", "device_retired", Severity.HIGH, f"{device.ownership} {device.platform} device is not retired and checked in {check_in_lag} days after end_date.", check_in_lag, [device.device_id]))
            else:
                checks.append(_fail("mdm", "device_retired", Severity.MEDIUM, f"{device.ownership} {device.platform} device is not retired.", days_since_end, [device.device_id]))
        return checks

    def _activity_checks(self, access: PersonAccess, end: date | None) -> list[RemovalCheck]:
        if end is None:
            return [_ok("audit", "activity_after_end", "No end_date, so post-departure activity can't be checked.", [], CheckStatus.INFO)]
        checks = []
        actor_ids = [a.account.account_id for a in access.idp] + [a.account.account_id for a in access.workspace] + [a.account.account_id for a in access.github]
        tolerance_end = end + timedelta(days=TIMEZONE_TOLERANCE_DAYS)
        events, total = self.audit_repo.get_events_by_actors_after(actor_ids, f"{tolerance_end.isoformat()}T23:59:59Z")
        _, total_incl_near = self.audit_repo.get_events_by_actors_after(actor_ids, f"{end.isoformat()}T23:59:59Z")
        if total:
            latest = _days_between(end, events[0].occurred_at)
            types = ", ".join(sorted({e.event_type for e in events}))
            checks.append(_fail("audit", "activity_after_end", Severity.CRITICAL, f"{total} audit events by this person's accounts more than {TIMEZONE_TOLERANCE_DAYS} day after end_date (latest {latest} days after; sample types: {types}).", latest, [e.event_id for e in events]))
        elif total_incl_near:
            near_events, _ = self.audit_repo.get_events_by_actors_after(actor_ids, f"{end.isoformat()}T23:59:59Z")
            checks.append(_fail("audit", "activity_near_end", Severity.LOW, f"{total_incl_near} audit events the UTC day after end_date; may still be the last local working day.", 1, [e.event_id for e in near_events]))
        else:
            checks.append(_ok("audit", "activity_after_end", "No audit events by this person's accounts after end_date.", []))

        last_seen = [(a.account.account_id, a.account.last_login_at) for a in access.idp] + [(a.account.account_id, a.account.last_login_at) for a in access.workspace]
        last_seen += [(a.account.account_id, a.account.last_active_at) for a in access.github]
        last_seen += [(row["access_id"], row["last_authenticated_at"]) for a in access.idp for row in a.app_access]
        lags = [(record_id, _days_between(end, ts)) for record_id, ts in last_seen]
        after_end = [(record_id, lag) for record_id, lag in lags if lag is not None and lag > TIMEZONE_TOLERANCE_DAYS]
        near_end = [(record_id, lag) for record_id, lag in lags if lag is not None and 0 < lag <= TIMEZONE_TOLERANCE_DAYS]
        if after_end:
            worst = max(lag for _, lag in after_end)
            checks.append(_fail("audit", "last_seen_after_end", Severity.CRITICAL, f"{len(after_end)} accounts or app records show a last login or activity more than {TIMEZONE_TOLERANCE_DAYS} day after end_date, up to {worst} days after.", worst, [record_id for record_id, _ in after_end]))
        if near_end:
            checks.append(_fail("audit", "last_seen_near_end", Severity.LOW, f"{len(near_end)} accounts or app records show a last login the UTC day after end_date; may be the last local working day or a deactivation timestamp.", 1, [record_id for record_id, _ in near_end]))
        return checks

    def _lifecycle_checks(self, access: PersonAccess) -> list[RemovalCheck]:
        target_ids = [access.person.person_id] + [a.account.account_id for a in access.idp] + [a.account.account_id for a in access.workspace] + [a.account.account_id for a in access.github]
        events = self.audit_repo.get_lifecycle_events(target_ids)
        if not events:
            return [_ok("audit", "offboarding_trail", "No HR termination, offboarding, or failure events were found for this person.", [], CheckStatus.INFO)]
        return [_ok("audit", "offboarding_trail", f"{e.occurred_at[:10]} {e.system} {e.event_type} ({e.outcome}): {e.details_json}", [e.event_id], CheckStatus.INFO) for e in events]
