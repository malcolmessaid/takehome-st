from pydantic import BaseModel, Field

from access_agent.services.person_access_service import PersonAccessService
from access_agent.tools.base import Tool


class FindPersonArgs(BaseModel):
    query: str = Field(description="Part of a name or email, or an exact person_id.")


def find_person(args: FindPersonArgs) -> list[dict]:
    return [p.model_dump() for p in PersonAccessService().find_person(args.query)]


TOOL = Tool(
    name="find_person",
    description="Find people by part of a name or email, or an exact person_id. Returns up to 10 candidates; if several match, ask the user which one they mean.",
    args_model=FindPersonArgs,
    fn=find_person,
)
