from pydantic import BaseModel, Field

from access_agent.services.access_review_service import AccessReviewService
from access_agent.tools.base import Tool


class GetLeftoverDirectGrantsArgs(BaseModel):
    person_id: str | None = Field(default=None, description="Limit to one person. Omit for everyone marked ended.")


def get_leftover_direct_grants(args: GetLeftoverDirectGrantsArgs) -> dict:
    return AccessReviewService().get_leftover_direct_grants(args.person_id)


TOOL = Tool(
    name="get_leftover_direct_grants",
    description=(
        "Direct grants still held by people who left: Drive permissions on their own account, GitHub collaborator grants, and Workspace OAuth grants. "
        "Offboarding only revokes group memberships and app access, so these are never cleaned up. Grants on a suspended GitHub account are dormant "
        "(unusable today, restored if reactivated). Grouped by person, most recent leaver first."
    ),
    args_model=GetLeftoverDirectGrantsArgs,
    fn=get_leftover_direct_grants,
)
