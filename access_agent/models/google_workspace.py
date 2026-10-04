from enum import StrEnum

from pydantic import BaseModel, Field


class WorkspaceAccountStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class WorkspaceMemberType(StrEnum):
    ACCOUNT = "account"
    GROUP = "group"


class WorkspaceMembershipRole(StrEnum):
    MEMBER = "member"
    MANAGER = "manager"
    OWNER = "owner"


class WorkspaceMembershipSource(StrEnum):
    MANUAL = "manual"
    IDP_SYNC = "idp_sync"


class DriveResourceType(StrEnum):
    FILE = "file"
    FOLDER = "folder"
    SHARED_DRIVE = "shared_drive"


class DriveClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class DrivePrincipalType(StrEnum):
    ACCOUNT = "account"
    GROUP = "group"
    DOMAIN = "domain"
    EXTERNAL_EMAIL = "external_email"


class DriveRole(StrEnum):
    VIEWER = "viewer"
    COMMENTER = "commenter"
    EDITOR = "editor"
    MANAGER = "manager"


class WorkspaceAccount(BaseModel):
    """A Google Workspace account as Google reports it. Links to the IdP only through person_id."""

    account_id: str = Field(description="Workspace account identifier, e.g. gwa_000001. Never equal to an IdP account_id.")
    person_id: str | None = Field(description="HR person this account belongs to.")
    primary_email: str = Field(description="Google account email.")
    status: WorkspaceAccountStatus = Field(description="Account state in Google. Can disagree with the IdP and HR.")
    created_at: str = Field(description="When the account was created (UTC ISO 8601).")
    last_login_at: str | None = Field(description="Most recent Google sign-in.")


class WorkspaceGroup(BaseModel):
    """A Google Workspace group. Drive files can be shared with groups."""

    group_id: str = Field(description="Workspace group identifier.")
    email: str = Field(description="Group email address.")
    name: str = Field(description="Group name.")
    description: str = Field(description="What the group is for.")
    created_at: str = Field(description="When the group was created (UTC ISO 8601).")


class WorkspaceGroupMembership(BaseModel):
    """One entry on a Workspace group's member list. The member is an account or another group (nesting)."""

    membership_id: str = Field(description="Membership identifier.")
    group_id: str = Field(description="The group the member belongs to.")
    member_type: WorkspaceMemberType = Field(description="Whether member_id is a Workspace account or another Workspace group.")
    member_id: str = Field(description="Workspace account_id or group_id, depending on member_type.")
    role: WorkspaceMembershipRole = Field(description="Member's role in the group.")
    source: WorkspaceMembershipSource = Field(description="Whether the membership was added by hand or pushed by the IdP.")
    granted_at: str = Field(description="When the membership started (UTC ISO 8601).")
    revoked_at: str | None = Field(description="When the membership was revoked. NULL means it is current.")


class DriveResource(BaseModel):
    """A Drive file, folder, or shared drive. Its owner has access without any permission row."""

    resource_id: str = Field(description="Drive resource identifier.")
    name: str = Field(description="File, folder, or shared drive name.")
    resource_type: DriveResourceType = Field(description="File, folder, or shared drive.")
    owner_account_id: str | None = Field(description="Workspace account that owns the resource. Ownership is an access path of its own.")
    classification: DriveClassification = Field(description="Data classification, from public to restricted.")
    created_at: str = Field(description="When the resource was created (UTC ISO 8601).")


class DrivePermission(BaseModel):
    """A sharing grant on a Drive resource to an account, group, whole domain, or external email address."""

    permission_id: str = Field(description="Permission identifier.")
    resource_id: str = Field(description="The Drive resource shared.")
    principal_type: DrivePrincipalType = Field(description="How to read principal_id: account, group, domain, or external email.")
    principal_id: str = Field(description="Workspace account_id, group_id, domain name, or external email, depending on principal_type.")
    role: DriveRole = Field(description="Access level granted.")
    granted_at: str = Field(description="When the permission was granted (UTC ISO 8601).")
    expires_at: str | None = Field(description="When the permission expires. Compare with the snapshot time even if revoked_at is NULL.")
    revoked_at: str | None = Field(description="When the permission was revoked. NULL means not explicitly revoked.")


class WorkspaceOauthGrant(BaseModel):
    """A third-party application a Workspace user authorized. There is no approved-app list or vendor-risk data."""

    grant_id: str = Field(description="OAuth grant identifier.")
    account_id: str = Field(description="Workspace account that authorized the app.")
    application_name: str = Field(description="Third-party application name.")
    client_id: str = Field(description="OAuth client ID of the third-party application.")
    scopes_json: str = Field(description="JSON list of permissions the app requested.")
    granted_at: str = Field(description="When the user authorized the app (UTC ISO 8601).")
    last_used_at: str | None = Field(description="When the app last used the grant.")
    revoked_at: str | None = Field(description="When the grant was revoked. NULL means it is current.")
