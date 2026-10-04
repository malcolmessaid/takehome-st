from pydantic import BaseModel

from access_agent.services.security_review_service import SecurityReviewService
from access_agent.tools.base import Tool


class FindRiskyOauthGrantsArgs(BaseModel):
    pass


def find_risky_oauth_grants(args: FindRiskyOauthGrantsArgs) -> dict:
    return SecurityReviewService().find_risky_oauth_grants()


TOOL = Tool(
    name="find_risky_oauth_grants",
    description=(
        "Current Workspace OAuth grants that give third-party apps sensitive scopes (mail, full Drive read, admin) or come from rarely authorized apps "
        "(2 or fewer accounts). Also lists every authorized app with how many accounts use it."
    ),
    args_model=FindRiskyOauthGrantsArgs,
    fn=find_risky_oauth_grants,
)
