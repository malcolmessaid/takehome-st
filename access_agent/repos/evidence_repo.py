from typing import Any

from access_agent.db import Database

ID_TABLES = {
    "per": ("people", "person_id"), "idpa": ("idp_accounts", "account_id"), "app": ("applications", "application_id"), "idpg": ("idp_groups", "group_id"),
    "idpm": ("idp_group_memberships", "membership_id"), "idpaa": ("idp_app_assignments", "assignment_id"), "aua": ("application_user_access", "access_id"),
    "gwa": ("workspace_accounts", "account_id"), "gwg": ("workspace_groups", "group_id"), "gwm": ("workspace_group_memberships", "membership_id"),
    "drv": ("drive_resources", "resource_id"), "drvp": ("drive_permissions", "permission_id"), "oag": ("workspace_oauth_grants", "grant_id"),
    "gha": ("github_accounts", "account_id"), "ghom": ("github_org_memberships", "membership_id"), "ght": ("github_teams", "team_id"),
    "ghtm": ("github_team_memberships", "membership_id"), "ghr": ("github_repositories", "repository_id"), "ghtrp": ("github_team_repo_permissions", "permission_id"),
    "ghrp": ("github_repo_collaborators", "permission_id"), "dev": ("devices", "device_id"), "evt": ("audit_events", "event_id"),
}


def id_prefix(record_id: str) -> str:
    return record_id.rsplit("_", 1)[0] if "_" in record_id else ""


class EvidenceRepo:
    """Looks up any record by its ID, whatever table it lives in."""

    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def get_records(self, record_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Returns found records keyed by ID. IDs with an unknown prefix or no matching row are simply absent."""
        by_prefix: dict[str, list[str]] = {}
        for record_id in set(record_ids):
            if id_prefix(record_id) in ID_TABLES:
                by_prefix.setdefault(id_prefix(record_id), []).append(record_id)
        records = {}
        for prefix, ids in by_prefix.items():
            table, pk = ID_TABLES[prefix]
            placeholders = ", ".join("?" for _ in ids)
            for row in self.db.query(f"SELECT * FROM {table} WHERE {pk} IN ({placeholders})", tuple(ids)):
                records[row[pk]] = {"table": table, **row}
        return records
