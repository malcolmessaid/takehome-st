from pydantic import BaseModel

from access_agent.services.security_review_service import SecurityReviewService
from access_agent.tools.base import Tool


class FindUnlinkedAccountsArgs(BaseModel):
    pass


def find_unlinked_accounts(args: FindUnlinkedAccountsArgs) -> dict:
    return SecurityReviewService().find_unlinked_accounts()


TOOL = Tool(
    name="find_unlinked_accounts",
    description=(
        "Active IdP, Workspace, and GitHub accounts with no linked person (service accounts, bots, unmatched users), with their org memberships, "
        "repo grants, app access, and audit activity. Nobody's offboarding removes these, so check who owns them."
    ),
    args_model=FindUnlinkedAccountsArgs,
    fn=find_unlinked_accounts,
)
