from access_agent.db import Database


class SqlRepo:
    """Runs arbitrary model-written SQL. Safety comes from the guards on Database, not from inspecting the text."""

    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def run_query(self, sql: str, max_rows: int) -> tuple[list[dict], bool]:
        """Returns up to max_rows rows and whether more rows were available."""
        rows = self.db.query(sql, max_rows=max_rows + 1)
        return rows[:max_rows], len(rows) > max_rows

    def get_schema_ddl(self) -> str:
        rows = self.db.query("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type DESC, name")
        return ";\n\n".join(r["sql"] for r in rows) + ";"
