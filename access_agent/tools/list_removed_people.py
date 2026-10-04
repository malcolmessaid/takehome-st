from pydantic import BaseModel, Field

from access_agent.services.removal_analysis_service import RemovalAnalysisService
from access_agent.tools.base import Tool


class ListRemovedPeopleArgs(BaseModel):
    since_days: int | None = Field(default=None, description="Only people whose end_date is within this many days before the snapshot. Omit for everyone who has left.")


def list_removed_people(args: ListRemovedPeopleArgs) -> dict:
    people = RemovalAnalysisService().list_removed_people(args.since_days)
    return {"count": len(people), "people": [p.model_dump(include={"person_id", "full_name", "worker_type", "department", "employment_status", "end_date"}) for p in people]}


TOOL = Tool(
    name="list_removed_people",
    description="People who have left: marked ended in HR, or with an end_date that has passed. Newest end_date first. Use before analyze_removal.",
    args_model=ListRemovedPeopleArgs,
    fn=list_removed_people,
)
