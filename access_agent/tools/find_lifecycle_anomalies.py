from pydantic import BaseModel, Field

from access_agent.services.security_review_service import SecurityReviewService
from access_agent.tools.base import Tool


class FindLifecycleAnomaliesArgs(BaseModel):
    limit: int = Field(default=25, ge=1, le=200, description="How many early-activity accounts to return (prehires first).")


def find_lifecycle_anomalies(args: FindLifecycleAnomaliesArgs) -> dict:
    return SecurityReviewService().find_lifecycle_anomalies(args.limit)


TOOL = Tool(
    name="find_lifecycle_anomalies",
    description=(
        "Timing that contradicts HR: accounts used before they were created or before the person's start date, and grants or memberships created after "
        "the person's end date (new access for someone who already left, not a missed removal). Early activity across many accounts is more likely a "
        "clock or data issue than misuse; check accounts_affected before concluding. Late grants are marked person_dates_inconsistent when the person's "
        "end date is before their start date (probably a rehire). See also find_hr_date_issues."
    ),
    args_model=FindLifecycleAnomaliesArgs,
    fn=find_lifecycle_anomalies,
)
