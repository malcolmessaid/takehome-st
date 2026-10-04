from enum import StrEnum

from pydantic import BaseModel, Field


class IdpAccountStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEPROVISIONED = "deprovisioned"


class ApplicationSensitivity(StrEnum):
    STANDARD = "standard"
    SENSITIVE = "sensitive"
    CRITICAL = "critical"


class AuthenticationMode(StrEnum):
    SSO = "sso"
    LOCAL = "local"
    MIXED = "mixed"


class MfaRequirement(StrEnum):
    REQUIRED = "required"
    CONDITIONAL = "conditional"
    OPTIONAL = "optional"


class GroupManagementType(StrEnum):
    MANUAL = "manual"
    HR_SYNC = "hr_sync"
    APPLICATION_SYNC = "application_sync"


class PrincipalType(StrEnum):
    ACCOUNT = "account"
    GROUP = "group"


class IdpMembershipSource(StrEnum):
    MANUAL = "manual"
    HR_SYNC = "hr_sync"
    GROUP_NESTING = "group_nesting"


class AppAccessStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class ProvisioningSource(StrEnum):
    IDP_SCIM = "idp_scim"
    MANUAL = "manual"
    APPLICATION_LOCAL = "application_local"


class MfaEnrollmentStatus(StrEnum):
    ENROLLED = "enrolled"
    NOT_ENROLLED = "not_enrolled"
    UNKNOWN = "unknown"


class IdpAccount(BaseModel):
    """A sign-in account in the identity provider (IdP), linked to an HR person."""

    account_id: str = Field(description="IdP account identifier, e.g. idpa_000001.")
    person_id: str | None = Field(description="HR person this account belongs to. Links to accounts in other systems only through this value.")
    username: str = Field(description="Sign-in username, usually the corporate email.")
    status: IdpAccountStatus = Field(description="Account state in the IdP. Can disagree with HR employment status.")
    created_at: str = Field(description="When the account was created (UTC ISO 8601).")
    deactivated_at: str | None = Field(description="When the account was deactivated, if it was.")
    last_login_at: str | None = Field(description="Most recent IdP sign-in.")


class Application(BaseModel):
    """An application in the catalog that the IdP can grant access to."""

    application_id: str = Field(description="Application identifier, e.g. app_0001.")
    name: str = Field(description="Application name, e.g. GitHub or Corporate VPN.")
    category: str = Field(description="Application category.")
    sensitivity: ApplicationSensitivity = Field(description="How sensitive the application is.")
    authentication_mode: AuthenticationMode = Field(description="Whether users sign in through SSO, a local login, or either.")
    default_mfa_requirement: MfaRequirement = Field(description="The app's general MFA policy. Policy only; it doesn't prove a user is enrolled or used MFA.")
    created_at: str = Field(description="When the application was added (UTC ISO 8601).")


class IdpGroup(BaseModel):
    """A named list in the IdP. Access is granted to groups, and groups can contain accounts or other groups."""

    group_id: str = Field(description="IdP group identifier.")
    name: str = Field(description="Group name, e.g. dept-customer-success.")
    description: str = Field(description="What the group is for.")
    management_type: GroupManagementType = Field(description="Whether membership is maintained by hand, from HR data, or by an application sync.")
    rule_expression: str | None = Field(description="Human-readable description of the membership rule. Not executable.")
    created_at: str = Field(description="When the group was created (UTC ISO 8601).")


class IdpGroupMembership(BaseModel):
    """One entry on an IdP group's member list. The member is an account or another group (nesting)."""

    membership_id: str = Field(description="Membership identifier.")
    group_id: str = Field(description="The group the member belongs to.")
    member_type: PrincipalType = Field(description="Whether member_id is an IdP account or another IdP group.")
    member_id: str = Field(description="IdP account_id or group_id, depending on member_type.")
    source: IdpMembershipSource = Field(description="How the member was added: by hand, by HR sync, or by group nesting.")
    granted_at: str = Field(description="When the membership started (UTC ISO 8601).")
    revoked_at: str | None = Field(description="When the membership was revoked. NULL means it is current.")


class IdpAppAssignment(BaseModel):
    """What the IdP is configured to grant: an application role assigned to an account or a group."""

    assignment_id: str = Field(description="Assignment identifier.")
    application_id: str = Field(description="The application granted.")
    principal_type: PrincipalType = Field(description="Whether principal_id is an IdP account or an IdP group.")
    principal_id: str = Field(description="IdP account_id or group_id, depending on principal_type. A group grant reaches nested members too.")
    role: str = Field(description="Role granted in the application.")
    granted_at: str = Field(description="When the assignment was made (UTC ISO 8601).")
    revoked_at: str | None = Field(description="When the assignment was revoked. NULL means it is current.")


class ApplicationUserAccess(BaseModel):
    """What an application reports about one IdP account's access. Can disagree with the IdP's assignments."""

    access_id: str = Field(description="Access record identifier.")
    application_id: str = Field(description="The application.")
    idp_account_id: str = Field(description="The IdP account this access belongs to.")
    role: str = Field(description="Role the application reports for this user.")
    status: AppAccessStatus = Field(description="Access state the application reports.")
    provisioning_source: ProvisioningSource = Field(description="idp_scim means created or updated by automated IdP sync; manual or application_local means managed outside the IdP.")
    assigned_at: str = Field(description="When access was assigned (UTC ISO 8601).")
    revoked_at: str | None = Field(description="When access was revoked, if it was.")
    mfa_enrollment_status: MfaEnrollmentStatus = Field(description="Whether the user is enrolled in MFA for this app. Enrollment doesn't prove MFA happened on every sign-in.")
    mfa_methods_json: str = Field(description="JSON list of registered MFA methods.")
    last_authenticated_at: str | None = Field(description="Most recent sign-in the application knows about.")
    last_authentication_method: str | None = Field(description="Method used for the most recent sign-in.")
    last_mfa_at: str | None = Field(description="Most recent sign-in that included MFA.")
