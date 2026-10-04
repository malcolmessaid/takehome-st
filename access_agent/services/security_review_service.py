import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from access_agent.logger import get_logger
from access_agent.repos.people_repo import PeopleRepo
from access_agent.repos.security_repo import SecurityRepo

logger = get_logger(__name__)

HIGH_PRIVILEGE = {"admin", "maintain", "owner"}
SENSITIVE_SCOPE_MARKERS = ("gmail", "mail.", "drive.readonly", "admin", "directory")
RARE_CLIENT_MAX_ACCOUNTS = 2
FOLLOW_UP_DAYS = 2
OWNER_FIELDS = ("system", "account_name", "status", "person_id", "full_name", "employment_status", "worker_type")


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")


def _details(event: dict) -> dict:
    try:
        return json.loads(event.get("details_json") or "{}")
    except json.JSONDecodeError:
        return {}


def _is_sensitive_scope(scope: str) -> bool:
    return scope in ("drive", "mail") or any(marker in scope for marker in SENSITIVE_SCOPE_MARKERS)


class SecurityReviewService:
    """General security checks across systems. Every result carries the record or event IDs to cite."""

    def __init__(self):
        self.repo = SecurityRepo()
        self.people_repo = PeopleRepo()

    def _owner(self, owners: dict, account_id: str | None) -> dict | None:
        owner = owners.get(account_id) if account_id else None
        return {k: owner[k] for k in OWNER_FIELDS} if owner else None

    def _annotate(self, events: list[dict]) -> list[dict]:
        """Adds who the actor is (account and person) and parses details_json."""
        owners = self.repo.get_account_owners([e["actor_id"] for e in events if e["actor_id"]])
        return [{**{k: v for k, v in e.items() if k != "details_json"}, "details": _details(e), "actor": self._owner(owners, e["actor_id"])} for e in events]

    def get_activity_timeline(self, around_event_id: str | None = None, window_minutes: int = 30, start: str | None = None, end: str | None = None,
                              person_id: str | None = None, ip_address: str | None = None, correlation_id: str | None = None,
                              systems: list[str] | None = None, include_routine: bool = True, limit: int = 100) -> dict:
        """Audit events in a time window, optionally narrowed to a person, IP, correlation ID, or system.

        With around_event_id, the window is centred on that event, and events sharing its IP or correlation ID at any time are returned too.
        """
        anchor, related = None, []
        if around_event_id:
            anchor = self.repo.get_event(around_event_id)
            if anchor is None:
                return {"error": f"No event {around_event_id}"}
            center = _parse(anchor["occurred_at"])
            start, end = _iso(center - timedelta(minutes=window_minutes)), _iso(center + timedelta(minutes=window_minutes))
            for field in ("correlation_id", "ip_address"):
                if anchor[field]:
                    rows, _ = self.repo.get_events(**{field: anchor[field]}, limit=50)
                    related += [r for r in rows if r["event_id"] != around_event_id and r["event_id"] not in {x["event_id"] for x in related}]
        account_ids = self.repo.get_account_ids_for_person(person_id) if person_id else None
        events, total = self.repo.get_events(start, end, account_ids, person_id, ip_address, correlation_id, systems, not include_routine, limit)
        logger.info(f"Activity timeline around_event_id={around_event_id} person_id={person_id} ip_address={ip_address} start={start} end={end} total={total}")
        return {
            "window": {"start": start, "end": end},
            "anchor_event": self._annotate([anchor])[0] if anchor else None,
            "total_events": total,
            "truncated": total > len(events),
            "events": self._annotate(events),
            "related_by_ip_or_correlation": self._annotate(related),
        }

    def find_change_events(self, since_days: int = 30, systems: list[str] | None = None, limit: int = 100) -> dict:
        """Non-routine audit events (grants, settings changes, authorizations, exceptions, lifecycle, failures), newest first, with risk flags.

        For grants to another account, also returns what that account did in the following FOLLOW_UP_DAYS days.
        """
        snapshot = _parse(self.people_repo.get_snapshot_time())
        events, total = self.repo.get_events(start=_iso(snapshot - timedelta(days=since_days)), systems=systems, exclude_routine=True, limit=limit)
        annotated = self._annotate(events)
        grantee_ids = [e["details"]["account_id"] for e in annotated if isinstance(e["details"].get("account_id"), str)]
        grantees = self.repo.get_account_owners(grantee_ids)
        for e in annotated:
            d, flags = e["details"], []
            if "approval_reference" in d and not d["approval_reference"]:
                flags.append("no_approval_reference")
            if str(d.get("permission", "")).lower() in HIGH_PRIVILEGE or str(d.get("role", "")).lower() in HIGH_PRIVILEGE:
                flags.append("high_privilege")
            if any(_is_sensitive_scope(s) for s in d.get("scopes", []) if isinstance(s, str)):
                flags.append("sensitive_scopes")
            if "->" in str(d.get("change", "")):
                flags.append("setting_changed")
            if e["outcome"] != "success":
                flags.append(f"outcome_{e['outcome']}")
            e["flags"] = flags
            grantee = d.get("account_id")
            if isinstance(grantee, str):
                e["grantee"] = self._owner(grantees, grantee)
                follow, follow_total = self.repo.get_events(start=e["occurred_at"], end=_iso(_parse(e["occurred_at"]) + timedelta(days=FOLLOW_UP_DAYS)), account_ids=[grantee], limit=20)
                e["grantee_follow_up"] = {"total": follow_total, "events": [{k: f[k] for k in ("event_id", "occurred_at", "event_type", "target_id", "ip_address")} for f in follow]}
        logger.info(f"Found change events since_days={since_days} total={total}")
        return {"since": _iso(snapshot - timedelta(days=since_days)), "total": total, "truncated": total > len(events), "events": list(reversed(annotated))}

    def find_privileged_access(self) -> dict:
        """Standing privileged access: GitHub org owners, application admins, and repo grants that are high-privilege or unapproved."""
        snapshot_at = self.people_repo.get_snapshot_time()
        owners = self.repo.get_org_owners()
        admins = self.repo.get_app_admins()
        grants = self.repo.get_current_collaborator_grants(snapshot_at, ("admin", "maintain", "write"))
        flagged = []
        for g in grants:
            flags = [f for f, hit in (("high_privilege", g["permission"] in HIGH_PRIVILEGE), ("no_approval_reference", not g["approval_reference"]),
                                      ("no_expiry", not g["expires_at"]), ("production_critical", g["sensitivity"] == "production_critical")) if hit]
            if "high_privilege" in flags or "no_approval_reference" in flags:
                flagged.append({**g, "flags": flags})
        person_ids = {r["person_id"] for r in owners + admins + flagged if r["person_id"]}
        people = {pid: self.people_repo.get_person(pid) for pid in person_ids}
        for r in owners + admins + flagged:
            p = people.get(r["person_id"])
            r["person"] = p.model_dump(include={"full_name", "employment_status", "worker_type", "end_date"}) if p else None
        logger.info(f"Found privileged access org_owner_count={len(owners)} app_admin_count={len(admins)} flagged_grant_count={len(flagged)}")
        return {"github_org_owners": owners, "application_admins": admins, "flagged_collaborator_grants": flagged}

    def find_risky_oauth_grants(self) -> dict:
        """Current OAuth grants with sensitive scopes (mail, full Drive, admin) or from rarely authorized apps."""
        grants = self.repo.get_current_oauth_grants_with_prevalence()
        risky = []
        for g in grants:
            scopes = json.loads(g["scopes_json"])
            flags = [f for f, hit in (("sensitive_scopes", any(_is_sensitive_scope(s) for s in scopes)), ("rare_app", g["accounts_with_client"] <= RARE_CLIENT_MAX_ACCOUNTS)) if hit]
            if flags:
                risky.append({**{k: v for k, v in g.items() if k != "scopes_json"}, "scopes": scopes, "flags": flags})
        people = {pid: self.people_repo.get_person(pid) for pid in {g["person_id"] for g in risky if g["person_id"]}}
        for g in risky:
            p = people.get(g["person_id"])
            g["person"] = p.model_dump(include={"full_name", "employment_status", "department", "end_date"}) if p else None
        apps = Counter((g["application_name"], g["accounts_with_client"]) for g in grants)
        logger.info(f"Found risky OAuth grants total_grants={len(grants)} risky_count={len(risky)}")
        return {"total_current_grants": len(grants), "apps": [{"application_name": a, "accounts": n} for (a, n) in sorted(apps, key=lambda x: x[1])], "risky_grants": risky}

    def find_mfa_gaps(self, application_name: str | None = None, sample_size: int = 20) -> dict:
        """Per-application MFA policy compared with enrollment, plus successful sign-ins that skipped required MFA."""
        apps = [a for a in self.repo.get_mfa_enrollment_by_application() if not application_name or a["application_name"].lower() == application_name.lower()]
        signins = [s for s in self.repo.get_signins_without_required_mfa() if not application_name or s["application_name"].lower() == application_name.lower()]
        by_app = defaultdict(list)
        for s in signins:
            by_app[s["application_name"]].append(s)
        for a in apps:
            app_signins = by_app[a["application_name"]]
            a["signins_without_required_mfa"] = len(app_signins)
            a["accounts_signing_in_without_mfa"] = len({s["actor_id"] for s in app_signins})
        owners = self.repo.get_account_owners([s["actor_id"] for s in signins[:sample_size]])
        sample = [{**s, "actor": self._owner(owners, s["actor_id"])} for s in signins[:sample_size]]
        logger.info(f"Found MFA gaps application_name={application_name} signin_count={len(signins)}")
        return {"by_application": apps, "total_signins_without_required_mfa": len(signins), "signin_sample": sample}

    def find_lifecycle_anomalies(self, limit: int = 25) -> dict:
        """Timing that contradicts the HR record: account activity before the account existed or before the person started,
        and grants created after the person's end date (new access for someone who already left, not a missed removal).

        Early activity is ranked prehires first (people who haven't started yet), then by event count. If it affects many accounts, it is more
        likely a clock or data-generation issue than misuse, so the total is returned for context. Late grants are marked when the person's own
        HR dates are inconsistent (end before start), since those are probably rehires rather than new access after leaving.
        """
        early = self.repo.get_activity_before_account_or_start()
        late = self.repo.get_grants_after_end_date()
        by_account = defaultdict(list)
        for e in early:
            by_account[e["account_id"]].append(e)
        early_summary = [{"account_id": acct, "person_id": rows[0]["person_id"], "account_created_at": rows[0]["account_created_at"], "start_date": rows[0]["start_date"],
                          "event_count": len(rows), "reasons": dict(Counter(r["reason"] for r in rows)), "first_event": rows[0]["occurred_at"], "last_event": rows[-1]["occurred_at"],
                          "event_ids": [r["event_id"] for r in rows][:20]} for acct, rows in by_account.items()]
        people = {pid: self.people_repo.get_person(pid) for pid in {r["person_id"] for r in early_summary + late if r["person_id"]}}
        for r in early_summary + late:
            p = people.get(r["person_id"])
            r["person"] = p.model_dump(include={"full_name", "employment_status", "worker_type", "start_date", "end_date"}) if p else None
        for r in late:
            p = people.get(r["person_id"])
            r["person_dates_inconsistent"] = bool(p and p.end_date and p.start_date and p.end_date < p.start_date)
        early_summary.sort(key=lambda r: ((r["person"] or {}).get("employment_status") != "prehire", -r["event_count"]))
        logger.info(f"Found lifecycle anomalies early_account_count={len(early_summary)} late_grant_count={len(late)}")
        return {
            "activity_before_account_or_start": {"accounts_affected": len(early_summary), "events": len(early), "prehire_accounts": sum(1 for r in early_summary if (r["person"] or {}).get("employment_status") == "prehire"), "top": early_summary[:limit]},
            "grants_after_end_date": {"total": len(late), "for_people_with_consistent_dates": sum(1 for r in late if not r["person_dates_inconsistent"]), "grants": late},
        }

    def find_unlinked_accounts(self) -> dict:
        """Active accounts in any system that aren't linked to a person, so no offboarding would ever remove them."""
        accounts = self.repo.get_active_unlinked_accounts()
        for a in accounts:
            for field in ("org_memberships", "collaborator_grants"):
                a[field] = a[field].split(",") if a[field] else []
        logger.info(f"Found unlinked accounts count={len(accounts)}")
        return {"count": len(accounts), "accounts": accounts}
