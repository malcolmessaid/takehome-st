from enum import StrEnum

from pydantic import BaseModel, Field


class RepoPermission(StrEnum):
    READ = "read"
    TRIAGE = "triage"
    WRITE = "write"
    MAINTAIN = "maintain"
    ADMIN = "admin"


class GithubAccountType(StrEnum):
    USER = "user"
    SERVICE = "service"


class GithubAccountStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class OrgRole(StrEnum):
    MEMBER = "member"
    OWNER = "owner"


class GithubMembershipSource(StrEnum):
    IDP_SCIM = "idp_scim"
    MANUAL = "manual"


class TeamRole(StrEnum):
    MEMBER = "member"
    MAINTAINER = "maintainer"


class RepoVisibility(StrEnum):
    PRIVATE = "private"
    INTERNAL = "internal"
    PUBLIC = "public"


class RepoSensitivity(StrEnum):
    STANDARD = "standard"
    SENSITIVE = "sensitive"
    PRODUCTION_CRITICAL = "production_critical"


class GithubAccount(BaseModel):
    """A GitHub account: a human user or a service account."""

    account_id: str = Field(description="GitHub account identifier, e.g. gha_000002.")
    person_id: str | None = Field(description="HR person this account belongs to. Service accounts and unmatched users may have none.")
    login: str = Field(description="GitHub username.")
    email: str | None = Field(description="Email on the GitHub account, if known.")
    account_type: GithubAccountType = Field(description="Human user or service account.")
    status: GithubAccountStatus = Field(description="Account state in GitHub.")
    created_at: str = Field(description="When the account was created (UTC ISO 8601).")
    last_active_at: str | None = Field(description="Most recent GitHub activity.")


class GithubOrgMembership(BaseModel):
    """Membership in the GitHub organization itself. Org owners can reach every repository without a team or collaborator grant."""

    membership_id: str = Field(description="Org membership identifier.")
    account_id: str = Field(description="The GitHub account.")
    org_role: OrgRole = Field(description="Member or owner of the organization.")
    source: GithubMembershipSource = Field(description="Whether the membership came from IdP sync or was added by hand.")
    granted_at: str = Field(description="When the membership started (UTC ISO 8601).")
    revoked_at: str | None = Field(description="When the membership was revoked. NULL means it is current.")


class GithubTeam(BaseModel):
    """A GitHub team. Teams get repository permissions, and some are synced from an IdP group."""

    team_id: str = Field(description="GitHub team identifier.")
    name: str = Field(description="Team name.")
    description: str = Field(description="What the team is for.")
    source_idp_group_id: str | None = Field(description="IdP group that syncs membership into this team, if any.")
    created_at: str = Field(description="When the team was created (UTC ISO 8601).")


class GithubTeamMembership(BaseModel):
    """One GitHub account on one team, current or historical. Teams don't nest."""

    membership_id: str = Field(description="Team membership identifier.")
    team_id: str = Field(description="The team.")
    account_id: str = Field(description="The GitHub account.")
    role: TeamRole = Field(description="Member or maintainer of the team.")
    source: GithubMembershipSource = Field(description="idp_scim means synced from the team's IdP group; manual means added by hand.")
    granted_at: str = Field(description="When the membership started (UTC ISO 8601).")
    revoked_at: str | None = Field(description="When the membership was revoked. NULL means it is current.")


class GithubRepository(BaseModel):
    """A GitHub repository."""

    repository_id: str = Field(description="Repository identifier.")
    name: str = Field(description="Repository name.")
    visibility: RepoVisibility = Field(description="Private, internal, or public.")
    sensitivity: RepoSensitivity = Field(description="How sensitive the repository is.")
    archived: bool = Field(description="Whether the repository is archived.")
    created_at: str = Field(description="When the repository was created (UTC ISO 8601).")


class GithubTeamRepoPermission(BaseModel):
    """A repository permission granted to a team. Combine with team membership to find which accounts receive it."""

    permission_id: str = Field(description="Permission identifier.")
    team_id: str = Field(description="The team granted access.")
    repository_id: str = Field(description="The repository.")
    permission: RepoPermission = Field(description="Access level granted.")
    granted_at: str = Field(description="When the permission was granted (UTC ISO 8601).")
    revoked_at: str | None = Field(description="When the permission was revoked. NULL means it is current.")


class GithubRepoCollaborator(BaseModel):
    """A repository permission granted directly to one account rather than through a team."""

    permission_id: str = Field(description="Permission identifier.")
    account_id: str = Field(description="The GitHub account granted access.")
    repository_id: str = Field(description="The repository.")
    permission: RepoPermission = Field(description="Access level granted.")
    approval_reference: str | None = Field(description="Reference to the approval for this grant. May be missing because source data is incomplete.")
    granted_at: str = Field(description="When the permission was granted (UTC ISO 8601).")
    expires_at: str | None = Field(description="When the permission expires. Compare with the snapshot time even if revoked_at is NULL.")
    revoked_at: str | None = Field(description="When the permission was revoked. NULL means not explicitly revoked.")
