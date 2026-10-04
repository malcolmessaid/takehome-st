from pydantic import BaseModel

from access_agent.services.access_review_service import AccessReviewService
from access_agent.tools.base import Tool


class GetLeftoverDirectGrantsArgs(BaseModel):
    pass


def get_leftover_direct_grants(args: GetLeftoverDirectGrantsArgs) -> dict:
    return AccessReviewService().get_leftover_direct_grants()


TOOL = Tool(
    name="get_leftover_direct_grants",
    description=(
        "Company-wide sweep of direct grants still held by everyone who left: Drive permissions on their own account, GitHub collaborator grants, and "
        "Workspace OAuth grants. Offboarding only revokes group memberships and app access, so these are never cleaned up. Grants on a suspended GitHub "
        "account are dormant (unusable today, restored if reactivated). For one person, use analyze_removal instead, which covers these and more."
    ),
    args_model=GetLeftoverDirectGrantsArgs,
    fn=get_leftover_direct_grants,
)
