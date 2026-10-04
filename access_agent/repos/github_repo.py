from typing import Any

from access_agent.db import Database
from access_agent.models.github import GithubAccount


class GithubRepo:
    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def get_first_account(self) -> GithubAccount | None:
        row = self.db.query_one("SELECT * FROM github_accounts LIMIT 1")
        return GithubAccount(**row) if row else None

    def get_accounts_for_person(self, person_id: str) -> list[GithubAccount]:
        return [GithubAccount(**r) for r in self.db.query("SELECT * FROM github_accounts WHERE person_id = ?", (person_id,))]

    def get_current_org_memberships(self, account_id: str) -> list[dict[str, Any]]:
        sql = "SELECT membership_id, org_role, source, granted_at FROM github_org_memberships WHERE account_id = ? AND revoked_at IS NULL"
        return self.db.query(sql, (account_id,))

    def get_current_team_memberships(self, account_id: str) -> list[dict[str, Any]]:
        sql = """
            SELECT tm.membership_id, tm.team_id, t.name AS team_name, tm.role, tm.source, t.source_idp_group_id, tm.granted_at
            FROM github_team_memberships tm JOIN github_teams t ON t.team_id = tm.team_id
            WHERE tm.account_id = ? AND tm.revoked_at IS NULL ORDER BY t.name
        """
        return self.db.query(sql, (account_id,))

    def get_current_team_repo_access(self, account_id: str) -> list[dict[str, Any]]:
        """Repository permissions the account gets through its current team memberships."""
        sql = """
            SELECT r.repository_id, r.name AS repository_name, r.sensitivity, r.visibility, r.archived,
                   p.permission, p.permission_id, tm.team_id, tm.membership_id AS team_membership_id
            FROM github_team_memberships tm
            JOIN github_team_repo_permissions p ON p.team_id = tm.team_id AND p.revoked_at IS NULL
            JOIN github_repositories r ON r.repository_id = p.repository_id
            WHERE tm.account_id = ? AND tm.revoked_at IS NULL ORDER BY r.name
        """
        return self.db.query(sql, (account_id,))

    def get_current_collaborator_access(self, account_id: str, snapshot_at: str) -> list[dict[str, Any]]:
        """Unrevoked, unexpired repository permissions granted directly to the account."""
        sql = """
            SELECT r.repository_id, r.name AS repository_name, r.sensitivity, r.visibility, r.archived,
                   c.permission, c.permission_id, c.approval_reference, c.granted_at, c.expires_at
            FROM github_repo_collaborators c JOIN github_repositories r ON r.repository_id = c.repository_id
            WHERE c.account_id = ? AND c.revoked_at IS NULL AND (c.expires_at IS NULL OR c.expires_at > ?) ORDER BY r.name
        """
        return self.db.query(sql, (account_id, snapshot_at))
