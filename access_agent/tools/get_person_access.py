from pydantic import BaseModel, Field

from access_agent.services.person_access_service import PersonAccessService
from access_agent.tools.base import Tool


class GetPersonAccessArgs(BaseModel):
    person_id: str = Field(description="HR person_id, e.g. per_000019. Use find_person first if you only have a name.")


def get_person_access(args: GetPersonAccessArgs) -> dict:
    access = PersonAccessService().get_person_access(args.person_id)
    return access.model_dump() if access else {"error": f"No person with person_id={args.person_id}"}


TOOL = Tool(
    name="get_person_access",
    description=(
        "Everything one person can currently reach: HR record, IdP accounts with groups and app access (each app shows which IdP assignment explains it), "
        "Google Workspace accounts with groups and Drive access, GitHub accounts with org, team, and repo access, and devices. All rows include record IDs to cite."
    ),
    args_model=GetPersonAccessArgs,
    fn=get_person_access,
)
