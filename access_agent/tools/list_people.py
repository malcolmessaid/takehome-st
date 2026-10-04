from pydantic import BaseModel, Field

from access_agent.models.people import EmploymentStatus, WorkerType
from access_agent.services.person_access_service import PersonAccessService
from access_agent.tools.base import Tool


class ListPeopleArgs(BaseModel):
    employment_status: EmploymentStatus | None = Field(default=None, description="Only people with this HR employment status.")
    worker_type: WorkerType | None = Field(default=None, description="Only employees or only contractors.")
    department: str | None = Field(default=None, description="Exact department name. The response lists valid departments.")
    limit: int = Field(default=25, le=100, description="Page size.")
    offset: int = Field(default=0, description="Rows to skip, for paging.")


def list_people(args: ListPeopleArgs) -> dict:
    return PersonAccessService().list_people(**args.model_dump())


TOOL = Tool(
    name="list_people",
    description=(
        "Overview of the HR roster: total counts by employment status and worker type, the list of departments, and one filtered page of people. "
        "Use for questions like 'who is in the system' or 'which contractors have ended'."
    ),
    args_model=ListPeopleArgs,
    fn=list_people,
)
