from typing import Any

from access_agent.db import Database
from access_agent.models.google_workspace import WorkspaceAccount

MAX_NESTING_DEPTH = 10

ACCOUNT_GROUPS_CTE = f"""
WITH RECURSIVE account_groups(group_id, membership_id, via_group_id, depth) AS (
    SELECT group_id, membership_id, NULL, 1 FROM workspace_group_memberships
    WHERE member_type = 'account' AND member_id = :account_id AND revoked_at IS NULL
    UNION
    SELECT m.group_id, m.membership_id, ag.group_id, ag.depth + 1 FROM account_groups ag
    JOIN workspace_group_memberships m ON m.member_type = 'group' AND m.member_id = ag.group_id AND m.revoked_at IS NULL
    WHERE ag.depth < {MAX_NESTING_DEPTH}
)
"""


class GoogleWorkspaceRepo:
    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def get_first_account(self) -> WorkspaceAccount | None:
        row = self.db.query_one("SELECT * FROM workspace_accounts LIMIT 1")
        return WorkspaceAccount(**row) if row else None

    def get_accounts_for_person(self, person_id: str) -> list[WorkspaceAccount]:
        return [WorkspaceAccount(**r) for r in self.db.query("SELECT * FROM workspace_accounts WHERE person_id = ?", (person_id,))]

    def get_current_group_memberships(self, account_id: str) -> list[dict[str, Any]]:
        """Direct and nested memberships. via_group_id is set when the membership is inherited through another group."""
        sql = ACCOUNT_GROUPS_CTE + """
            SELECT ag.group_id, g.name AS group_name, g.email AS group_email, ag.membership_id, ag.via_group_id, ag.depth
            FROM account_groups ag JOIN workspace_groups g ON g.group_id = ag.group_id ORDER BY ag.depth, g.name
        """
        return self.db.query(sql, {"account_id": account_id})

    def get_current_oauth_grants(self, account_id: str) -> list[dict[str, Any]]:
        sql = "SELECT grant_id, application_name, scopes_json, granted_at, last_used_at FROM workspace_oauth_grants WHERE account_id = ? AND revoked_at IS NULL"
        return self.db.query(sql, (account_id,))

    def get_direct_drive_permissions_of_ended_people(self, snapshot_at: str, person_id: str | None = None) -> list[dict[str, Any]]:
        """Unrevoked, unexpired Drive permissions granted directly to the Workspace account of someone marked ended."""
        sql = """
            SELECT w.person_id, w.account_id, w.status AS account_status, p.permission_id, p.role, p.granted_at,
                   r.resource_id, r.name AS resource_name, r.classification
            FROM people pe JOIN workspace_accounts w ON w.person_id = pe.person_id
            JOIN drive_permissions p ON p.principal_type = 'account' AND p.principal_id = w.account_id
            JOIN drive_resources r ON r.resource_id = p.resource_id
            WHERE pe.employment_status = 'ended' AND (:person_id IS NULL OR pe.person_id = :person_id)
              AND p.revoked_at IS NULL AND (p.expires_at IS NULL OR p.expires_at > :snapshot_at)
            ORDER BY w.person_id, r.name
        """
        return self.db.query(sql, {"snapshot_at": snapshot_at, "person_id": person_id})

    def get_oauth_grants_of_ended_people(self, person_id: str | None = None) -> list[dict[str, Any]]:
        sql = """
            SELECT w.person_id, w.account_id, w.status AS account_status, g.grant_id, g.application_name, g.granted_at, g.last_used_at
            FROM people pe JOIN workspace_accounts w ON w.person_id = pe.person_id JOIN workspace_oauth_grants g ON g.account_id = w.account_id
            WHERE pe.employment_status = 'ended' AND (:person_id IS NULL OR pe.person_id = :person_id) AND g.revoked_at IS NULL
            ORDER BY w.person_id, g.application_name
        """
        return self.db.query(sql, {"person_id": person_id})

    def get_owned_resources(self, account_id: str) -> list[dict[str, Any]]:
        sql = "SELECT resource_id, name AS resource_name, resource_type, classification FROM drive_resources WHERE owner_account_id = ? ORDER BY name"
        return self.db.query(sql, (account_id,))

    def get_current_drive_permissions(self, account_id: str, email_domain: str, snapshot_at: str) -> list[dict[str, Any]]:
        """Unrevoked, unexpired permissions granted to the account, any of its groups, or its email domain."""
        sql = ACCOUNT_GROUPS_CTE + """
            SELECT p.permission_id, p.principal_type, p.principal_id, p.role, p.granted_at, p.expires_at,
                   r.resource_id, r.name AS resource_name, r.resource_type, r.classification
            FROM drive_permissions p JOIN drive_resources r ON r.resource_id = p.resource_id
            WHERE p.revoked_at IS NULL AND (p.expires_at IS NULL OR p.expires_at > :snapshot_at) AND (
                (p.principal_type = 'account' AND p.principal_id = :account_id)
                OR (p.principal_type = 'group' AND p.principal_id IN (SELECT group_id FROM account_groups))
                OR (p.principal_type = 'domain' AND p.principal_id = :email_domain)
            )
            ORDER BY r.name
        """
        return self.db.query(sql, {"account_id": account_id, "email_domain": email_domain, "snapshot_at": snapshot_at})
