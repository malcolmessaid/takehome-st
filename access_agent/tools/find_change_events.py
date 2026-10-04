from pydantic import BaseModel, Field

from access_agent.models.audit_log import AuditSystem
from access_agent.services.security_review_service import SecurityReviewService
from access_agent.tools.base import Tool


class FindChangeEventsArgs(BaseModel):
    since_days: int = Field(default=30, ge=1, le=400, description="How many days before the snapshot to look back.")
    systems: list[AuditSystem] | None = Field(default=None, description="Only these systems.")
    limit: int = Field(default=100, ge=1, le=500, description="Maximum events to return.")


def find_change_events(args: FindChangeEventsArgs) -> dict:
    return SecurityReviewService().find_change_events(args.since_days, args.systems, args.limit)


TOOL = Tool(
    name="find_change_events",
    description=(
        "Non-routine audit events (access grants, settings changes, OAuth authorizations, exceptions, lifecycle and failure events), newest first. "
        "Each is flagged for missing approval reference, high privilege, sensitive scopes, or a changed setting. Grants to another account include what "
        "that account did in the next 2 days. Start here for 'what changed recently' or 'anything suspicious'."
    ),
    args_model=FindChangeEventsArgs,
    fn=find_change_events,
)
