from typing import Any

from access_agent.db import Database
from access_agent.models.identity_provider import IdpAccount

MAX_NESTING_DEPTH = 10

ACCOUNT_GROUPS_CTE = f"""
WITH RECURSIVE account_groups(group_id, membership_id, via_group_id, depth) AS (
    SELECT group_id, membership_id, NULL, 1 FROM idp_group_memberships
    WHERE member_type = 'account' AND member_id = :account_id AND revoked_at IS NULL
    UNION
    SELECT m.group_id, m.membership_id, ag.group_id, ag.depth + 1 FROM account_groups ag
    JOIN idp_group_memberships m ON m.member_type = 'group' AND m.member_id = ag.group_id AND m.revoked_at IS NULL
    WHERE ag.depth < {MAX_NESTING_DEPTH}
)
"""

ALL_ACCOUNT_GROUPS_CTE = f"""
WITH RECURSIVE all_account_groups(account_id, group_id, depth) AS (
    SELECT member_id, group_id, 1 FROM idp_group_memberships WHERE member_type = 'account' AND revoked_at IS NULL
    UNION
    SELECT aag.account_id, m.group_id, aag.depth + 1 FROM all_account_groups aag
    JOIN idp_group_memberships m ON m.member_type = 'group' AND m.member_id = aag.group_id AND m.revoked_at IS NULL
    WHERE aag.depth < {MAX_NESTING_DEPTH}
)
"""


class IdentityProviderRepo:
    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def get_first_account(self) -> IdpAccount | None:
        row = self.db.query_one("SELECT * FROM idp_accounts LIMIT 1")
        return IdpAccount(**row) if row else None

    def get_accounts_for_person(self, person_id: str) -> list[IdpAccount]:
        return [IdpAccount(**r) for r in self.db.query("SELECT * FROM idp_accounts WHERE person_id = ?", (person_id,))]

    def get_current_group_memberships(self, account_id: str) -> list[dict[str, Any]]:
        """Direct and nested memberships. via_group_id is set when the membership is inherited through another group."""
        sql = ACCOUNT_GROUPS_CTE + """
            SELECT ag.group_id, g.name AS group_name, g.management_type, ag.membership_id, ag.via_group_id, ag.depth
            FROM account_groups ag JOIN idp_groups g ON g.group_id = ag.group_id ORDER BY ag.depth, g.name
        """
        return self.db.query(sql, {"account_id": account_id})

    def get_app_access(self, account_id: str) -> list[dict[str, Any]]:
        """Every application_user_access row for the account (any status), with application details."""
        sql = """
            SELECT u.*, a.name AS application_name, a.sensitivity, a.default_mfa_requirement
            FROM application_user_access u JOIN applications a ON a.application_id = u.application_id
            WHERE u.idp_account_id = ? ORDER BY a.name
        """
        return self.db.query(sql, (account_id,))

    def get_current_app_assignments(self, account_id: str) -> list[dict[str, Any]]:
        """Current IdP assignments that reach the account directly or through any of its groups."""
        sql = ACCOUNT_GROUPS_CTE + """
            SELECT x.assignment_id, x.application_id, a.name AS application_name, x.role, x.principal_type, x.principal_id
            FROM idp_app_assignments x JOIN applications a ON a.application_id = x.application_id
            WHERE x.revoked_at IS NULL AND (
                (x.principal_type = 'group' AND x.principal_id IN (SELECT group_id FROM account_groups))
                OR (x.principal_type = 'account' AND x.principal_id = :account_id)
            )
        """
        return self.db.query(sql, {"account_id": account_id})

    def get_assigned_app_pairs(self, application_name: str | None = None) -> list[dict[str, Any]]:
        """Every account-application pair a current assignment reaches (directly or through nested groups), joined to what the
        application reports. access_id is NULL when the application has no row for that account."""
        sql = ALL_ACCOUNT_GROUPS_CTE + """, assigned AS (
                SELECT account_id, application_id, MIN(assignment_id) AS assignment_id FROM (
                    SELECT aag.account_id, x.application_id, x.assignment_id FROM all_account_groups aag
                    JOIN idp_app_assignments x ON x.principal_type = 'group' AND x.principal_id = aag.group_id AND x.revoked_at IS NULL
                    UNION ALL
                    SELECT principal_id, application_id, assignment_id FROM idp_app_assignments WHERE principal_type = 'account' AND revoked_at IS NULL
                ) GROUP BY account_id, application_id
            )
            SELECT s.account_id, a.status AS account_status, a.person_id, p.full_name, p.employment_status,
                   s.application_id, ap.name AS application_name, s.assignment_id, u.access_id, u.status AS access_status
            FROM assigned s
            JOIN idp_accounts a ON a.account_id = s.account_id
            LEFT JOIN people p ON p.person_id = a.person_id
            JOIN applications ap ON ap.application_id = s.application_id
            LEFT JOIN application_user_access u ON u.idp_account_id = s.account_id AND u.application_id = s.application_id
            WHERE :application_name IS NULL OR ap.name = :application_name COLLATE NOCASE
            ORDER BY ap.name, s.account_id
        """
        return self.db.query(sql, {"application_name": application_name})

    def get_accounts_deactivated_before_created(self) -> list[dict[str, Any]]:
        sql = "SELECT account_id, person_id, username, status, created_at, deactivated_at FROM idp_accounts WHERE deactivated_at < created_at ORDER BY account_id"
        return self.db.query(sql)

    def get_app_access_revoked_before_assigned(self) -> list[dict[str, Any]]:
        sql = """
            SELECT u.access_id, u.idp_account_id, a.person_id, ap.name AS application_name, u.assigned_at, u.revoked_at
            FROM application_user_access u JOIN idp_accounts a ON a.account_id = u.idp_account_id JOIN applications ap ON ap.application_id = u.application_id
            WHERE u.revoked_at < u.assigned_at ORDER BY u.idp_account_id, ap.name
        """
        return self.db.query(sql)
