from pydantic import BaseModel, Field

from access_agent.models.audit_log import AuditSystem
from access_agent.services.security_review_service import SecurityReviewService
from access_agent.tools.base import Tool


class GetActivityTimelineArgs(BaseModel):
    around_event_id: str | None = Field(default=None, description="Centre the window on this event, and also return events sharing its IP or correlation ID at any time.")
    window_minutes: int = Field(default=30, ge=1, le=10080, description="Minutes before and after around_event_id.")
    start: str | None = Field(default=None, description="Window start (ISO 8601 UTC). Ignored when around_event_id is set.")
    end: str | None = Field(default=None, description="Window end (ISO 8601 UTC). Ignored when around_event_id is set.")
    person_id: str | None = Field(default=None, description="Only events where any of this person's accounts (or the person) is the actor or target.")
    ip_address: str | None = Field(default=None, description="Only events from this IP address.")
    correlation_id: str | None = Field(default=None, description="Only events sharing this correlation ID.")
    systems: list[AuditSystem] | None = Field(default=None, description="Only these systems.")
    include_routine: bool = Field(default=False, description="True also returns high-volume routine events (logins, fetches, views, check-ins). Only needed when narrowed to one person, IP, or correlation ID.")
    limit: int = Field(default=100, ge=1, le=200, description="Maximum events to return, oldest first.")


def get_activity_timeline(args: GetActivityTimelineArgs) -> dict:
    return SecurityReviewService().get_activity_timeline(args.around_event_id, args.window_minutes, args.start, args.end, args.person_id, args.ip_address, args.correlation_id, args.systems, args.include_routine, args.limit)


TOOL = Tool(
    name="get_activity_timeline",
    description=(
        "Audit events across all systems in a time window, with each actor resolved to its account and person. Narrow by person, IP, correlation ID, or system. "
        "Use around_event_id to see what happened just before and after a suspicious event, and what else came from the same IP or correlation ID."
    ),
    args_model=GetActivityTimelineArgs,
    fn=get_activity_timeline,
)
