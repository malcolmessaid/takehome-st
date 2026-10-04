import json

from access_agent.tools import (
    analyze_removal, find_change_events, find_hr_date_issues, find_lifecycle_anomalies, find_mfa_gaps, find_person, find_privileged_access, find_risky_oauth_grants,
    find_unlinked_accounts, get_activity_timeline, get_leftover_direct_grants, get_person_access, list_people, list_removed_people, read_code, reconcile_app_assignments,
    run_sql, submit_report,
)
from access_agent.tools.base import Tool

TOOLS: dict[str, Tool] = {t.name: t for t in [
    list_people.TOOL, find_person.TOOL, get_person_access.TOOL, list_removed_people.TOOL, analyze_removal.TOOL, get_leftover_direct_grants.TOOL,
    reconcile_app_assignments.TOOL, find_hr_date_issues.TOOL, get_activity_timeline.TOOL, find_change_events.TOOL, find_privileged_access.TOOL,
    find_risky_oauth_grants.TOOL, find_mfa_gaps.TOOL, find_lifecycle_anomalies.TOOL, find_unlinked_accounts.TOOL, submit_report.TOOL,
]}
SQL_TOOLS: dict[str, Tool] = {t.name: t for t in [run_sql.TOOL, read_code.TOOL, submit_report.SQL_TOOL]}


def execute_tool(name: str, raw_arguments: str, tools: dict[str, Tool] = TOOLS) -> str:
    """Validates arguments, runs the tool, and returns JSON. Errors are returned to the model rather than raised."""
    tool = tools.get(name)
    if tool is None or tool.fn is None:
        return json.dumps({"error": f"Unknown tool {name}"})
    try:
        result = tool.fn(tool.args_model.model_validate_json(raw_arguments or "{}"))
    except Exception as e:
        result = {"error": f"{type(e).__name__}: {e}"}
    return json.dumps(result, default=str)
