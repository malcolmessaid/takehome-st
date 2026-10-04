from pydantic import BaseModel, Field

from access_agent.services.security_review_service import SecurityReviewService
from access_agent.tools.base import Tool


class FindMfaGapsArgs(BaseModel):
    application_name: str | None = Field(default=None, description="Limit to one application, e.g. 'Snowflake'. Omit for all.")
    sample_size: int = Field(default=20, ge=0, le=100, description="How many example sign-ins without required MFA to return.")


def find_mfa_gaps(args: FindMfaGapsArgs) -> dict:
    return SecurityReviewService().find_mfa_gaps(args.application_name, args.sample_size)


TOOL = Tool(
    name="find_mfa_gaps",
    description=(
        "Per application: MFA policy, how many active accounts are enrolled, not enrolled, or unknown, and how many successful sign-ins skipped MFA "
        "the event says was required. Includes sample sign-ins with the account and person."
    ),
    args_model=FindMfaGapsArgs,
    fn=find_mfa_gaps,
)
