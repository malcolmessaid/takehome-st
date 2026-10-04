from pydantic import BaseModel, Field

from access_agent.services.security_review_service import SecurityReviewService
from access_agent.tools.base import Tool


class FindPrivilegedAccessArgs(BaseModel):
    include_all_grants: bool = Field(default=False, description="True returns every flagged repo grant, including routine unapproved write grants on standard repos. Usually not needed.")


def find_privileged_access(args: FindPrivilegedAccessArgs) -> dict:
    return SecurityReviewService().find_privileged_access(args.include_all_grants)


TOOL = Tool(
    name="find_privileged_access",
    description=(
        "Standing privileged access: GitHub org owners, application admins, and repo collaborator grants that are admin/maintain or lack an approval "
        "reference. By default returns notable grants in full (admin/maintain, sensitive or production repos, or held by an inactive account or person) "
        "and counts the rest. Includes each holder's person and employment status."
    ),
    args_model=FindPrivilegedAccessArgs,
    fn=find_privileged_access,
)
