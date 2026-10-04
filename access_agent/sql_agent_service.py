from access_agent.agent_service import SYSTEM_PROMPT, AgentService
from access_agent.llm_client import LLMClient
from access_agent.repos.people_repo import PeopleRepo
from access_agent.repos.sql_repo import SqlRepo
from access_agent.tools.read_code import PROJECT_ROOT
from access_agent.tools.registry import SQL_TOOLS

SQL_MAX_STEPS = 40

SQL_PROMPT_ADDENDUM = """

You answer by writing your own SQL with the run_sql tool. Run as many read-only queries as you need.
- Start small: check counts and a few rows before pulling detail. Prefer aggregates over dumping tables.
- Use the snapshot time above, not the real current date, for "current" and "after end date" comparisons.
- The project's repos (read_code, e.g. access_agent/repos/identity_provider_repo.py) contain tested SQL for nested groups, current Drive permissions, and current GitHub access. Read them when a join is non-obvious.
- If a query errors, read the error, fix the SQL, and retry.

=== SCHEMA GUIDE (input_data/SCHEMA.md) ===
{schema_guide}

=== DDL ===
{ddl}"""


class SqlAgentService(AgentService):
    """Same loop as AgentService, but the model writes its own read-only SQL instead of using purpose-built tools."""

    def __init__(self, llm: LLMClient | None = None):
        schema_guide = (PROJECT_ROOT / "input_data" / "SCHEMA.md").read_text()
        prompt = SYSTEM_PROMPT.format(snapshot_at=PeopleRepo().get_snapshot_time()) + SQL_PROMPT_ADDENDUM.format(schema_guide=schema_guide, ddl=SqlRepo().get_schema_ddl())
        super().__init__(llm=llm, tools=SQL_TOOLS, system_prompt=prompt, max_steps=SQL_MAX_STEPS)
