from access_agent.models.report import InvestigationReport
from access_agent.tools.base import Tool

SUBMIT_REPORT = "submit_report"

TOOL = Tool(
    name=SUBMIT_REPORT,
    description="Submit the final investigation report. Call this exactly once at the end of an investigation.",
    args_model=InvestigationReport,
)
