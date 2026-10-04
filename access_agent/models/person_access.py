from typing import Any

from pydantic import BaseModel, Field

from access_agent.models.devices import Device
from access_agent.models.github import GithubAccount
from access_agent.models.google_workspace import WorkspaceAccount
from access_agent.models.identity_provider import IdpAccount
from access_agent.models.people import Person


class IdpAccess(BaseModel):
    """What one IdP account can reach."""

    account: IdpAccount
    group_memberships: list[dict[str, Any]] = Field(description="Current direct and nested IdP group memberships.")
    app_access: list[dict[str, Any]] = Field(description="Every application_user_access row (any status), each with the current IdP assignments that explain it.")
    assigned_but_not_reported: list[dict[str, Any]] = Field(description="Current IdP assignments for apps where the application reports no access row.")


class WorkspaceAccess(BaseModel):
    """What one Google Workspace account can reach."""

    account: WorkspaceAccount
    group_memberships: list[dict[str, Any]] = Field(description="Current direct and nested Workspace group memberships.")
    owned_resources: list[dict[str, Any]] = Field(description="Drive resources this account owns (access without any permission row).")
    drive_permissions: list[dict[str, Any]] = Field(description="Unrevoked, unexpired Drive permissions reaching the account directly, through a group, or through its domain.")


class GithubAccess(BaseModel):
    """What one GitHub account can reach."""

    account: GithubAccount
    org_memberships: list[dict[str, Any]] = Field(description="Current organization memberships. An owner can reach every repository.")
    team_memberships: list[dict[str, Any]] = Field(description="Current team memberships.")
    team_repo_access: list[dict[str, Any]] = Field(description="Repository permissions received through current teams.")
    collaborator_access: list[dict[str, Any]] = Field(description="Unrevoked, unexpired repository permissions granted directly to the account.")


class PersonAccess(BaseModel):
    """Everything one person can currently reach across systems, as of the snapshot."""

    snapshot_at: str
    person: Person
    idp: list[IdpAccess]
    workspace: list[WorkspaceAccess]
    github: list[GithubAccess]
    devices: list[Device]
