from collections import defaultdict

from access_agent.logger import get_logger
from access_agent.repos.github_repo import GithubRepo
from access_agent.repos.google_workspace_repo import GoogleWorkspaceRepo
from access_agent.repos.identity_provider_repo import IdentityProviderRepo
from access_agent.repos.people_repo import PeopleRepo

logger = get_logger(__name__)

PERSON_FIELDS = {"person_id", "full_name", "worker_type", "employment_status", "start_date", "end_date"}


class AccessReviewService:
    """Company-wide checks that look across people rather than at one person."""

    def __init__(self):
        self.people_repo = PeopleRepo()
        self.idp_repo = IdentityProviderRepo()
        self.workspace_repo = GoogleWorkspaceRepo()
        self.github_repo = GithubRepo()

    def reconcile_app_assignments(self, application_name: str | None = None, sample_size: int = 20) -> dict:
        """Compares what IdP assignments grant with what each application reports.

        Returns per-application coverage, every pair where the application reports non-active access despite a current
        assignment (usually small and interesting), and a sample of pairs with no application row at all.
        """
        pairs = self.idp_repo.get_assigned_app_pairs(application_name)
        logger.info(f"Reconciling app assignments application_name={application_name} pair_count={len(pairs)}")
        by_app: dict[str, dict] = defaultdict(lambda: {"assigned": 0, "active": 0, "not_active": 0, "missing_row": 0, "assignment_ids": set()})
        for p in pairs:
            app = by_app[p["application_name"]]
            app["assigned"] += 1
            app["assignment_ids"].add(p["assignment_id"])
            app["missing_row" if p["access_id"] is None else "active" if p["access_status"] == "active" else "not_active"] += 1
        coverage = [{"application_name": name, **{k: v for k, v in c.items() if k != "assignment_ids"}, "coverage_pct": round(100 * (c["assigned"] - c["missing_row"]) / c["assigned"], 1), "assignment_ids": sorted(c["assignment_ids"])} for name, c in sorted(by_app.items(), key=lambda kv: kv[1]["missing_row"] / kv[1]["assigned"], reverse=True)]
        missing = [p for p in pairs if p["access_id"] is None]
        return {
            "total_assigned_pairs": len(pairs),
            "total_missing_row": len(missing),
            "coverage_by_application": coverage,
            "not_active_despite_assignment": [p for p in pairs if p["access_id"] is not None and p["access_status"] != "active"],
            "missing_row_by_employment_status": {status: sum(1 for p in missing if p["employment_status"] == status) for status in sorted({str(p["employment_status"]) for p in missing})},
            "missing_row_sample": missing[:sample_size],
        }

    def find_hr_date_issues(self) -> dict:
        """People and records whose dates are in an impossible order. These break any 'days since leaving' calculation."""
        people = self.people_repo.get_people_with_end_before_start()
        accounts = self.idp_repo.get_accounts_deactivated_before_created()
        access = self.idp_repo.get_app_access_revoked_before_assigned()
        logger.info(f"Found HR date issues people_count={len(people)} account_count={len(accounts)} access_row_count={len(access)}")
        return {
            "people_end_before_start": [p.model_dump(include=PERSON_FIELDS) for p in people],
            "idp_accounts_deactivated_before_created": accounts,
            "app_access_revoked_before_assigned": access,
        }

    def get_leftover_direct_grants(self, person_id: str | None = None) -> dict:
        """Direct grants (Drive permissions, GitHub collaborator grants, OAuth grants) still held by people marked ended.

        Offboarding in this snapshot only revokes group memberships and application access, so these are never cleaned up.
        A grant on a suspended GitHub account is dormant: unusable today, but restored if the account is reactivated.
        """
        snapshot_at = self.people_repo.get_snapshot_time()
        drive = self.workspace_repo.get_direct_drive_permissions_of_ended_people(snapshot_at, person_id)
        github = self.github_repo.get_collaborator_grants_of_ended_people(snapshot_at, person_id)
        oauth = self.workspace_repo.get_oauth_grants_of_ended_people(person_id)
        logger.info(f"Found leftover direct grants person_id={person_id} drive_count={len(drive)} github_count={len(github)} oauth_count={len(oauth)}")
        people: dict[str, dict] = {}
        for kind, rows in (("drive_permissions", drive), ("github_collaborator_grants", github), ("oauth_grants", oauth)):
            for row in rows:
                if row["person_id"] not in people:
                    person = self.people_repo.get_person(row["person_id"])
                    people[row["person_id"]] = {**person.model_dump(include=PERSON_FIELDS), "drive_permissions": [], "github_collaborator_grants": [], "oauth_grants": []}
                people[row["person_id"]][kind].append({k: v for k, v in row.items() if k != "person_id"})
        return {"snapshot_at": snapshot_at, "people_count": len(people), "people": sorted(people.values(), key=lambda p: p["end_date"] or "", reverse=True)}
