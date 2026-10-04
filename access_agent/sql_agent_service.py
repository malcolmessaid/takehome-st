import json
import re
from datetime import datetime
from pathlib import Path

from access_agent.agent_service import SYSTEM_PROMPT, AgentService
from access_agent.llm_client import LLMClient
from access_agent.logger import get_logger
from access_agent.models.proposed_tool import SqlInvestigationReport
from access_agent.models.report import InvestigationReport
from access_agent.repos.people_repo import PeopleRepo
from access_agent.repos.sql_repo import SqlRepo
from access_agent.tools.read_code import PROJECT_ROOT
from access_agent.tools.registry import SQL_TOOLS

logger = get_logger(__name__)

SQL_MAX_STEPS = 40
RUNS_DIR = PROJECT_ROOT / "investigations" / "runs"

SQL_PROMPT_ADDENDUM = """

You answer by writing your own SQL with the run_sql tool. Run as many read-only queries as you need.
- Start small: check counts and a few rows before pulling detail. Prefer aggregates over dumping tables.
- Use the snapshot time above, not the real current date, for "current" and "after end date" comparisons.
- The project's repos (read_code, e.g. access_agent/repos/identity_provider_repo.py) contain tested SQL for nested groups, current Drive permissions, and current GitHub access. Read them when a join is non-obvious.
- If a query errors, read the error, fix the SQL, and retry.
- Give every run_sql call a short purpose.

Your queries will be turned into reusable tools. In submit_report, fill proposed_tools with 1 to 5 tools generalized from the queries that produced your evidence:
- Replace hardcoded IDs, names, and dates with :name placeholders (e.g. :person_id, :snapshot_at, :since_date). Only use placeholders that are listed in parameters.
- Each tool is one SELECT that returns the ID columns a report would cite, plus enough context to explain them.
- Prefer tools a future agent would reuse for other people or questions over one-off queries.
- example_args must reproduce this investigation's evidence. The system runs each tool with them to check it works.

=== SCHEMA GUIDE (input_data/SCHEMA.md) ===
{schema_guide}

=== DDL ===
{ddl}"""


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:50]


class SqlAgentService(AgentService):
    """Same loop as AgentService, but the model writes its own read-only SQL and proposes reusable tools from it."""

    def __init__(self, llm: LLMClient | None = None):
        schema_guide = (PROJECT_ROOT / "input_data" / "SCHEMA.md").read_text()
        prompt = SYSTEM_PROMPT.format(snapshot_at=PeopleRepo().get_snapshot_time()) + SQL_PROMPT_ADDENDUM.format(schema_guide=schema_guide, ddl=SqlRepo().get_schema_ddl())
        super().__init__(llm=llm, tools=SQL_TOOLS, system_prompt=prompt, max_steps=SQL_MAX_STEPS)
        self.last_run_path: Path | None = None

    def run(self, user_message: str) -> InvestigationReport | str:
        result = super().run(user_message)
        if isinstance(result, SqlInvestigationReport):
            self._validate_proposed_tools(result)
        self.last_run_path = self._save_run(user_message, result)
        return result

    def _validate_proposed_tools(self, report: SqlInvestigationReport) -> None:
        """Runs each proposed tool's SQL with its example_args so broken proposals are visible before anyone builds them."""
        repo = SqlRepo()
        for tool in report.proposed_tools:
            try:
                rows, truncated = repo.run_query(tool.sql, max_rows=500, params=tool.example_args)
                tool.validation = f"ok: {len(rows)}{'+' if truncated else ''} rows"
            except Exception as e:
                tool.validation = f"error: {type(e).__name__}: {e}"
            logger.info(f"Validated proposed tool tool_name={tool.name} validation={tool.validation}")

    def _save_run(self, question: str, result: InvestigationReport | str) -> Path:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        path = RUNS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{_slug(question)}.json"
        queries = [{"step": t["step"], "purpose": t["arguments"].get("purpose"), "sql": t["arguments"].get("sql"), "result_chars": t["result_chars"], "error": t["error"]} for t in self.trace if t["tool"] == "run_sql"]
        run = {"question": question, "model": self.llm.model, "queries": queries, "other_tool_calls": [t for t in self.trace if t["tool"] != "run_sql"], "report": result.model_dump() if isinstance(result, InvestigationReport) else result}
        path.write_text(json.dumps(run, indent=2, default=str))
        logger.info(f"Saved SQL agent run path={path} query_count={len(queries)}")
        return path
