from typing import Any

from access_agent.db import Database

ROUTINE_EVENT_TYPES = (
    "user.login", "application.authentication", "repository.fetched", "repository.pushed", "pull_request.reviewed", "drive.resource.viewed",
    "oauth.token.used", "device.checked_in", "policy.evaluated", "group.membership.evaluated", "worker.record.updated",
)

ALL_ACCOUNTS_SQL = """
    SELECT account_id, person_id, 'idp' AS system, username AS account_name, status, created_at FROM idp_accounts
    UNION ALL SELECT account_id, person_id, 'workspace', primary_email, status, created_at FROM workspace_accounts
    UNION ALL SELECT account_id, person_id, 'github', login, status, created_at FROM github_accounts
"""


def _in(values: list[str] | tuple[str, ...], prefix: str) -> tuple[str, dict]:
    """Named placeholders for an IN clause, e.g. ':a0, :a1', and their params."""
    params = {f"{prefix}{i}": v for i, v in enumerate(values)}
    return ", ".join(f":{k}" for k in params), params


class SecurityRepo:
    """Cross-system queries for security reviews: audit timelines, changes, privileged access, MFA, and lifecycle anomalies."""

    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def get_account_owners(self, account_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Maps IdP, Workspace, and GitHub account IDs to the account and its person (person fields NULL when unlinked)."""
        if not account_ids:
            return {}
        placeholders, params = _in(sorted(set(account_ids)), "a")
        sql = f"""
            SELECT a.*, p.full_name, p.employment_status, p.worker_type, p.start_date, p.end_date
            FROM ({ALL_ACCOUNTS_SQL}) a LEFT JOIN people p ON p.person_id = a.person_id WHERE a.account_id IN ({placeholders})
        """
        return {r["account_id"]: r for r in self.db.query(sql, params)}

    def get_account_ids_for_person(self, person_id: str) -> list[str]:
        return [r["account_id"] for r in self.db.query(f"SELECT account_id FROM ({ALL_ACCOUNTS_SQL}) WHERE person_id = ?", (person_id,))]

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        return self.db.query_one("SELECT * FROM audit_events WHERE event_id = ?", (event_id,))

    def get_events(self, start: str | None = None, end: str | None = None, account_ids: list[str] | None = None, person_id: str | None = None,
                   ip_address: str | None = None, correlation_id: str | None = None, systems: list[str] | None = None,
                   exclude_routine: bool = False, limit: int = 100) -> tuple[list[dict[str, Any]], int]:
        """Audit events matching every given filter, oldest first, and the total count. account_ids match actor or target."""
        clauses, params = [], {"limit": limit}
        if start:
            clauses.append("occurred_at >= :start")
            params["start"] = start
        if end:
            clauses.append("occurred_at <= :end")
            params["end"] = end
        if account_ids or person_id:
            ids = [*(account_ids or []), *([person_id] if person_id else [])]
            placeholders, id_params = _in(ids, "id")
            clauses.append(f"(actor_id IN ({placeholders}) OR target_id IN ({placeholders}))")
            params.update(id_params)
        if ip_address:
            clauses.append("ip_address = :ip_address")
            params["ip_address"] = ip_address
        if correlation_id:
            clauses.append("correlation_id = :correlation_id")
            params["correlation_id"] = correlation_id
        if systems:
            placeholders, sys_params = _in(systems, "s")
            clauses.append(f"system IN ({placeholders})")
            params.update(sys_params)
        if exclude_routine:
            placeholders, routine_params = _in(ROUTINE_EVENT_TYPES, "r")
            clauses.append(f"event_type NOT IN ({placeholders})")
            params.update(routine_params)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total = self.db.query_one(f"SELECT COUNT(*) AS n FROM audit_events {where}", params)["n"]
        return self.db.query(f"SELECT * FROM audit_events {where} ORDER BY occurred_at LIMIT :limit", params), total

    def get_org_owners(self) -> list[dict[str, Any]]:
        sql = """
            SELECT m.membership_id, m.org_role, m.source, m.granted_at, g.account_id, g.login, g.account_type, g.status AS account_status, g.person_id
            FROM github_org_memberships m JOIN github_accounts g ON g.account_id = m.account_id WHERE m.revoked_at IS NULL AND m.org_role = 'owner'
        """
        return self.db.query(sql)

    def get_app_admins(self) -> list[dict[str, Any]]:
        sql = """
            SELECT u.access_id, ap.name AS application_name, ap.sensitivity, u.role, u.provisioning_source, u.assigned_at, u.mfa_enrollment_status,
                   a.account_id, a.status AS account_status, a.person_id
            FROM application_user_access u JOIN applications ap ON ap.application_id = u.application_id JOIN idp_accounts a ON a.account_id = u.idp_account_id
            WHERE u.status = 'active' AND u.role = 'admin' ORDER BY ap.name
        """
        return self.db.query(sql)

    def get_current_collaborator_grants(self, snapshot_at: str, permissions: tuple[str, ...]) -> list[dict[str, Any]]:
        placeholders, params = _in(permissions, "p")
        sql = f"""
            SELECT c.permission_id, c.permission, c.approval_reference, c.granted_at, c.expires_at, r.repository_id, r.name AS repository_name, r.sensitivity,
                   g.account_id, g.login, g.account_type, g.status AS account_status, g.person_id
            FROM github_repo_collaborators c JOIN github_repositories r ON r.repository_id = c.repository_id JOIN github_accounts g ON g.account_id = c.account_id
            WHERE c.revoked_at IS NULL AND (c.expires_at IS NULL OR c.expires_at > :snapshot_at) AND c.permission IN ({placeholders})
            ORDER BY c.granted_at DESC
        """
        return self.db.query(sql, {"snapshot_at": snapshot_at, **params})

    def get_current_oauth_grants_with_prevalence(self) -> list[dict[str, Any]]:
        """Every unrevoked OAuth grant, with how many accounts have authorized the same client."""
        sql = """
            SELECT g.grant_id, g.application_name, g.client_id, g.scopes_json, g.granted_at, g.last_used_at, w.account_id, w.primary_email, w.status AS account_status,
                   w.person_id, COUNT(*) OVER (PARTITION BY g.client_id) AS accounts_with_client
            FROM workspace_oauth_grants g JOIN workspace_accounts w ON w.account_id = g.account_id WHERE g.revoked_at IS NULL
        """
        return self.db.query(sql)

    def get_mfa_enrollment_by_application(self) -> list[dict[str, Any]]:
        sql = """
            SELECT ap.application_id, ap.name AS application_name, ap.sensitivity, ap.default_mfa_requirement, COUNT(*) AS active_accounts,
                   SUM(u.mfa_enrollment_status = 'enrolled') AS enrolled, SUM(u.mfa_enrollment_status = 'not_enrolled') AS not_enrolled,
                   SUM(u.mfa_enrollment_status = 'unknown') AS unknown
            FROM application_user_access u JOIN applications ap ON ap.application_id = u.application_id WHERE u.status = 'active'
            GROUP BY ap.application_id ORDER BY ap.name
        """
        return self.db.query(sql)

    def get_signins_without_required_mfa(self) -> list[dict[str, Any]]:
        """Successful sign-ins where the event says MFA was required but not performed."""
        sql = """
            SELECT e.event_id, e.occurred_at, e.actor_id, e.target_id AS application_id, ap.name AS application_name, e.ip_address,
                   json_extract(e.details_json, '$.authentication_method') AS authentication_method
            FROM audit_events e JOIN applications ap ON ap.application_id = e.target_id
            WHERE e.event_type = 'application.authentication' AND e.outcome = 'success'
              AND json_extract(e.details_json, '$.mfa_requirement') = 'required' AND json_extract(e.details_json, '$.mfa_performed') = 0
            ORDER BY e.occurred_at DESC
        """
        return self.db.query(sql)

    def get_activity_before_account_or_start(self) -> list[dict[str, Any]]:
        """Events by an account before the account was created or before its person's start date."""
        sql = f"""
            SELECT e.event_id, e.occurred_at, e.system, e.event_type, e.outcome, e.ip_address, a.account_id, a.created_at AS account_created_at,
                   a.person_id, p.start_date, CASE WHEN e.occurred_at < a.created_at THEN 'before_account_created' ELSE 'before_start_date' END AS reason
            FROM audit_events e JOIN ({ALL_ACCOUNTS_SQL}) a ON a.account_id = e.actor_id LEFT JOIN people p ON p.person_id = a.person_id
            WHERE e.occurred_at < a.created_at OR (p.start_date IS NOT NULL AND substr(e.occurred_at, 1, 10) < p.start_date)
            ORDER BY a.account_id, e.occurred_at
        """
        return self.db.query(sql)

    def get_grants_after_end_date(self) -> list[dict[str, Any]]:
        """Grants and memberships created for someone after their HR end_date (a new grant, not a missed removal)."""
        sql = """
            SELECT 'drive_permission' AS grant_type, d.permission_id AS grant_id, d.granted_at, r.name AS granted_on, r.classification AS detail, p.person_id, p.end_date
            FROM drive_permissions d JOIN workspace_accounts w ON d.principal_type = 'account' AND d.principal_id = w.account_id
            JOIN people p ON p.person_id = w.person_id JOIN drive_resources r ON r.resource_id = d.resource_id WHERE substr(d.granted_at, 1, 10) > p.end_date
            UNION ALL
            SELECT 'github_collaborator', c.permission_id, c.granted_at, gr.name, c.permission, p.person_id, p.end_date
            FROM github_repo_collaborators c JOIN github_accounts g ON g.account_id = c.account_id JOIN people p ON p.person_id = g.person_id
            JOIN github_repositories gr ON gr.repository_id = c.repository_id WHERE substr(c.granted_at, 1, 10) > p.end_date
            UNION ALL
            SELECT 'oauth_grant', o.grant_id, o.granted_at, o.application_name, o.scopes_json, p.person_id, p.end_date
            FROM workspace_oauth_grants o JOIN workspace_accounts w ON w.account_id = o.account_id JOIN people p ON p.person_id = w.person_id
            WHERE substr(o.granted_at, 1, 10) > p.end_date
            UNION ALL
            SELECT 'idp_group_membership', m.membership_id, m.granted_at, g.name, NULL, p.person_id, p.end_date
            FROM idp_group_memberships m JOIN idp_accounts a ON m.member_type = 'account' AND m.member_id = a.account_id JOIN people p ON p.person_id = a.person_id
            JOIN idp_groups g ON g.group_id = m.group_id WHERE substr(m.granted_at, 1, 10) > p.end_date
            UNION ALL
            SELECT 'workspace_group_membership', m.membership_id, m.granted_at, g.name, NULL, p.person_id, p.end_date
            FROM workspace_group_memberships m JOIN workspace_accounts w ON m.member_type = 'account' AND m.member_id = w.account_id
            JOIN people p ON p.person_id = w.person_id JOIN workspace_groups g ON g.group_id = m.group_id WHERE substr(m.granted_at, 1, 10) > p.end_date
            UNION ALL
            SELECT 'application_access', u.access_id, u.assigned_at, ap.name, u.status, p.person_id, p.end_date
            FROM application_user_access u JOIN idp_accounts a ON a.account_id = u.idp_account_id JOIN people p ON p.person_id = a.person_id
            JOIN applications ap ON ap.application_id = u.application_id WHERE substr(u.assigned_at, 1, 10) > p.end_date
            ORDER BY granted_at DESC
        """
        return self.db.query(sql)

    def get_active_unlinked_accounts(self) -> list[dict[str, Any]]:
        """Active accounts in any system with no linked person, with their privileges and activity."""
        sql = f"""
            SELECT a.*,
                   (SELECT MAX(occurred_at) FROM audit_events e WHERE e.actor_id = a.account_id) AS last_event_at,
                   (SELECT COUNT(*) FROM audit_events e WHERE e.actor_id = a.account_id) AS event_count,
                   (SELECT group_concat(membership_id || ':' || org_role) FROM github_org_memberships m WHERE m.account_id = a.account_id AND m.revoked_at IS NULL) AS org_memberships,
                   (SELECT group_concat(c.permission_id || ':' || r.name || ':' || c.permission || ':' || r.sensitivity) FROM github_repo_collaborators c
                      JOIN github_repositories r ON r.repository_id = c.repository_id WHERE c.account_id = a.account_id AND c.revoked_at IS NULL) AS collaborator_grants,
                   (SELECT COUNT(*) FROM application_user_access u WHERE u.idp_account_id = a.account_id AND u.status = 'active') AS active_app_access
            FROM ({ALL_ACCOUNTS_SQL}) a WHERE a.person_id IS NULL AND a.status = 'active'
        """
        return self.db.query(sql)
