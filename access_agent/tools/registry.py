import json

from access_agent.tools import find_person, get_person_access, list_people, submit_report
from access_agent.tools.base import Tool

TOOLS: dict[str, Tool] = {t.name: t for t in [list_people.TOOL, find_person.TOOL, get_person_access.TOOL, submit_report.TOOL]}


def execute_tool(name: str, raw_arguments: str) -> str:
    """Validates arguments, runs the tool, and returns JSON. Errors are returned to the model rather than raised."""
    tool = TOOLS.get(name)
    if tool is None or tool.fn is None:
        return json.dumps({"error": f"Unknown tool {name}"})
    try:
        result = tool.fn(tool.args_model.model_validate_json(raw_arguments or "{}"))
    except Exception as e:
        result = {"error": f"{type(e).__name__}: {e}"}
    return json.dumps(result, default=str)
