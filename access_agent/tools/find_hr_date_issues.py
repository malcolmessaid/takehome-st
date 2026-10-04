from pydantic import BaseModel

from access_agent.services.access_review_service import AccessReviewService
from access_agent.tools.base import Tool


class FindHrDateIssuesArgs(BaseModel):
    pass


def find_hr_date_issues(args: FindHrDateIssuesArgs) -> dict:
    return AccessReviewService().find_hr_date_issues()


TOOL = Tool(
    name="find_hr_date_issues",
    description=(
        "Find records with dates in an impossible order: people whose end_date is before their start_date, IdP accounts deactivated before they "
        "were created, and application access revoked before it was assigned. Often a rehire whose old end date was never cleared. Check this "
        "before trusting 'days since leaving' for a person."
    ),
    args_model=FindHrDateIssuesArgs,
    fn=find_hr_date_issues,
)
