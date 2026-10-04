from enum import StrEnum

from pydantic import BaseModel, Field


class AuditSystem(StrEnum):
    HR = "hr"
    IDP = "idp"
    WORKSPACE = "workspace"
    GITHUB = "github"
    MDM = "mdm"


class ActorType(StrEnum):
    ACCOUNT = "account"
    SERVICE = "service"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class EventSource(StrEnum):
    CONSOLE = "console"
    SYNC = "sync"
    API = "api"
    USER_ACTION = "user_action"


class EventOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


class AuditEvent(BaseModel):
    """One event from a source system's audit log. Logs are incomplete: an event can prove an action happened without proving which human caused it."""

    event_id: str = Field(description="Stable event identifier. Cite this as evidence.")
    occurred_at: str = Field(description="When the event happened (UTC ISO 8601).")
    system: AuditSystem = Field(description="Source system that recorded the event.")
    event_type: str = Field(description="Event name, e.g. application.authentication or user.login. Not limited to a fixed list.")
    actor_type: ActorType = Field(description="What kind of actor initiated the event. Read with actor_id.")
    actor_id: str | None = Field(description="ID of the initiating account or service; interpret using actor_type.")
    target_type: str = Field(description="Kind of record affected, e.g. account, application, group, repository, device.")
    target_id: str = Field(description="ID of the affected record; interpret using target_type.")
    source: EventSource = Field(description="Whether the event came from a console, sync, API, or user action.")
    outcome: EventOutcome = Field(description="Whether the action succeeded, failed, or partially succeeded.")
    ip_address: str | None = Field(description="Source IP address, when recorded.")
    correlation_id: str | None = Field(description="Shared by related events, when available.")
    details_json: str = Field(description="JSON text with event-specific fields, e.g. whether MFA was performed during a sign-in.")
