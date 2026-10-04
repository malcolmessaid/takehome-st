from pydantic import BaseModel, Field

from access_agent.services.removal_analysis_service import RemovalAnalysisService
from access_agent.tools.base import Tool


class AnalyzeRemovalArgs(BaseModel):
    person_id: str = Field(description="HR person_id of someone who has left, e.g. per_001941.")


def analyze_removal(args: AnalyzeRemovalArgs) -> dict:
    analysis = RemovalAnalysisService().analyze_person(args.person_id)
    return analysis.model_dump() if analysis else {"error": f"No person with person_id={args.person_id}"}


TOOL = Tool(
    name="analyze_removal",
    description=(
        "Offboarding check for one person who has left. Compares every account, group, app, Drive, GitHub, and device record against their end_date, "
        "checks for activity after they left, and lists HR and offboarding events. Each check has status (fail/pass/info), severity, days_after_end, "
        "age (recent or long_standing), and evidence IDs. Leftover access always fails, however recent."
    ),
    args_model=AnalyzeRemovalArgs,
    fn=analyze_removal,
)
