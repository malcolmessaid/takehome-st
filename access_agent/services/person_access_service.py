from access_agent.logger import get_logger
from access_agent.models.people import Person
from access_agent.models.person_access import GithubAccess, IdpAccess, PersonAccess, WorkspaceAccess
from access_agent.repos.github_repo import GithubRepo
from access_agent.repos.google_workspace_repo import GoogleWorkspaceRepo
from access_agent.repos.identity_provider_repo import IdentityProviderRepo
from access_agent.repos.people_repo import PeopleRepo

logger = get_logger(__name__)


class PersonAccessService:
    def __init__(self):
        self.people_repo = PeopleRepo()
        self.idp_repo = IdentityProviderRepo()
        self.workspace_repo = GoogleWorkspaceRepo()
        self.github_repo = GithubRepo()

    def find_person(self, query: str) -> list[Person]:
        """Candidates matching a name, email, or person_id. Several results means the caller must disambiguate."""
        logger.info(f"Finding person query={query}")
        return self.people_repo.find_people(query)

    def list_people(self, employment_status: str | None = None, worker_type: str | None = None, department: str | None = None, limit: int = 25, offset: int = 0) -> dict:
        """Overall counts plus one filtered page of people, so the caller never needs the whole roster."""
        logger.info(f"Listing people employment_status={employment_status} worker_type={worker_type} department={department} limit={limit} offset={offset}")
        people, total = self.people_repo.list_people(employment_status, worker_type, department, limit, offset)
        return {
            "counts_by_status_and_worker_type": self.people_repo.get_people_counts(),
            "departments": self.people_repo.get_departments(),
            "total_matching": total,
            "returned": len(people),
            "offset": offset,
            "people": [p.model_dump(include={"person_id", "full_name", "primary_email", "department", "title", "worker_type", "employment_status"}) for p in people],
        }

    def get_person_access(self, person_id: str) -> PersonAccess | None:
        """Everything the person can currently reach in the IdP, Google Workspace, and GitHub, plus their devices."""
        logger.info(f"Getting person access person_id={person_id}")
        person = self.people_repo.get_person(person_id)
        if person is None:
            return None
        snapshot_at = self.people_repo.get_snapshot_time()
        return PersonAccess(
            snapshot_at=snapshot_at,
            person=person,
            idp=[self._get_idp_access(a) for a in self.idp_repo.get_accounts_for_person(person_id)],
            workspace=[self._get_workspace_access(a, snapshot_at) for a in self.workspace_repo.get_accounts_for_person(person_id)],
            github=[self._get_github_access(a, snapshot_at) for a in self.github_repo.get_accounts_for_person(person_id)],
            devices=self.people_repo.get_devices_for_person(person_id),
        )

    def _get_idp_access(self, account) -> IdpAccess:
        app_access = self.idp_repo.get_app_access(account.account_id)
        assignments = self.idp_repo.get_current_app_assignments(account.account_id)
        for row in app_access:
            row["explained_by_assignments"] = [x for x in assignments if x["application_id"] == row["application_id"]]
        reported_apps = {row["application_id"] for row in app_access}
        return IdpAccess(
            account=account,
            group_memberships=self.idp_repo.get_current_group_memberships(account.account_id),
            app_access=app_access,
            assigned_but_not_reported=[x for x in assignments if x["application_id"] not in reported_apps],
        )

    def _get_workspace_access(self, account, snapshot_at: str) -> WorkspaceAccess:
        email_domain = account.primary_email.split("@")[-1]
        return WorkspaceAccess(
            account=account,
            group_memberships=self.workspace_repo.get_current_group_memberships(account.account_id),
            owned_resources=self.workspace_repo.get_owned_resources(account.account_id),
            drive_permissions=self.workspace_repo.get_current_drive_permissions(account.account_id, email_domain, snapshot_at),
        )

    def _get_github_access(self, account, snapshot_at: str) -> GithubAccess:
        return GithubAccess(
            account=account,
            org_memberships=self.github_repo.get_current_org_memberships(account.account_id),
            team_memberships=self.github_repo.get_current_team_memberships(account.account_id),
            team_repo_access=self.github_repo.get_current_team_repo_access(account.account_id),
            collaborator_access=self.github_repo.get_current_collaborator_access(account.account_id, snapshot_at),
        )
