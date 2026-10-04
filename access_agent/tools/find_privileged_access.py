from pydantic import BaseModel

from access_agent.services.security_review_service import SecurityReviewService
from access_agent.tools.base import Tool


class FindPrivilegedAccessArgs(BaseModel):
    pass


def find_privileged_access(args: FindPrivilegedAccessArgs) -> dict:
    return SecurityReviewService().find_privileged_access()


TOOL = Tool(
    name="find_privileged_access",
    description=(
        "Standing privileged access: GitHub org owners, application admins, and current repo collaborator grants that are admin/maintain or lack an "
        "approval reference (flagged with no_expiry and production_critical where relevant). Includes each holder's person and employment status."
    ),
    args_model=FindPrivilegedAccessArgs,
    fn=find_privileged_access,
)
