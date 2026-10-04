from pydantic import BaseModel, Field

from access_agent.repos.sql_repo import SqlRepo
from access_agent.tools.base import Tool

MAX_ROWS_LIMIT = 500


class RunSqlArgs(BaseModel):
    sql: str = Field(description="One read-only SQLite SELECT statement (WITH and WITH RECURSIVE are allowed).")
    max_rows: int = Field(default=100, ge=1, le=MAX_ROWS_LIMIT, description="Maximum rows to return. Prefer aggregates over large dumps.")


def run_sql(args: RunSqlArgs) -> dict:
    rows, truncated = SqlRepo().run_query(args.sql, args.max_rows)
    return {"row_count": len(rows), "truncated": truncated, "rows": rows}


TOOL = Tool(
    name="run_sql",
    description="Run one read-only SELECT against the access snapshot. Writes, PRAGMA, ATTACH, and multiple statements are rejected. Queries time out after 10 seconds.",
    args_model=RunSqlArgs,
    fn=run_sql,
)
