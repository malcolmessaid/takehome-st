import json

from access_agent.tools import analyze_removal, find_person, get_person_access, list_people, list_removed_people, read_code, run_sql, submit_report
from access_agent.tools.base import Tool

TOOLS: dict[str, Tool] = {t.name: t for t in [list_people.TOOL, find_person.TOOL, get_person_access.TOOL, list_removed_people.TOOL, analyze_removal.TOOL, submit_report.TOOL]}
SQL_TOOLS: dict[str, Tool] = {t.name: t for t in [run_sql.TOOL, read_code.TOOL, submit_report.TOOL]}


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
