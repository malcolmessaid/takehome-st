import json
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, Field

from access_agent.models.people import EmploymentStatus, WorkerType
from access_agent.models.report import InvestigationReport
from access_agent.services.person_access_service import PersonAccessService

SUBMIT_REPORT = "submit_report"


class FindPersonArgs(BaseModel):
    query: str = Field(description="Part of a name or email, or an exact person_id.")


class PersonIdArgs(BaseModel):
    person_id: str = Field(description="HR person_id, e.g. per_000019. Use find_person first if you only have a name.")


class ListPeopleArgs(BaseModel):
    employment_status: EmploymentStatus | None = Field(default=None, description="Only people with this HR employment status.")
    worker_type: WorkerType | None = Field(default=None, description="Only employees or only contractors.")
    department: str | None = Field(default=None, description="Exact department name. The response lists valid departments.")
    limit: int = Field(default=25, le=100, description="Page size.")
    offset: int = Field(default=0, description="Rows to skip, for paging.")


def find_person(args: FindPersonArgs) -> Any:
    return [p.model_dump() for p in PersonAccessService().find_person(args.query)]


def get_person_access(args: PersonIdArgs) -> Any:
    access = PersonAccessService().get_person_access(args.person_id)
    return access.model_dump() if access else {"error": f"No person with person_id={args.person_id}"}


def list_people(args: ListPeopleArgs) -> Any:
    return PersonAccessService().list_people(**args.model_dump())


@dataclass
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    fn: Callable[[Any], Any] | None

    def schema(self) -> dict:
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.args_model.model_json_schema()}}


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("list_people", "Overview of the HR roster: total counts by employment status and worker type, the list of departments, and one filtered page of people. Use for questions like 'who is in the system' or 'which contractors have ended'.", ListPeopleArgs, list_people),
    Tool("find_person", "Find people by part of a name or email, or an exact person_id. Returns up to 10 candidates; if several match, ask the user which one they mean.", FindPersonArgs, find_person),
    Tool("get_person_access", "Everything one person can currently reach: HR record, IdP accounts with groups and app access (each app shows which IdP assignment explains it), Google Workspace accounts with groups and Drive access, GitHub accounts with org, team, and repo access, and devices. All rows include record IDs to cite.", PersonIdArgs, get_person_access),
    Tool(SUBMIT_REPORT, "Submit the final investigation report. Call this exactly once at the end of an investigation.", InvestigationReport, None),
]}


def execute_tool(name: str, raw_arguments: str) -> str:
    tool = TOOLS.get(name)
    if tool is None or tool.fn is None:
        return json.dumps({"error": f"Unknown tool {name}"})
    try:
        result = tool.fn(tool.args_model.model_validate_json(raw_arguments or "{}"))
    except Exception as e:
        result = {"error": f"{type(e).__name__}: {e}"}
    return json.dumps(result, default=str)
