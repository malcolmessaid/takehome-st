import os
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "input_data" / "access_snapshot.sqlite"


class Database:
    """Read-only singleton connection to the access snapshot."""

    _instance: "Database | None" = None

    def __new__(cls) -> "Database":
        if cls._instance is None:
            db_path = Path(os.environ.get("ACCESS_DB_PATH", DEFAULT_DB_PATH))
            instance = super().__new__(cls)
            instance.conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
            instance.conn.row_factory = sqlite3.Row
            cls._instance = instance
        return cls._instance

    def query(self, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in self.conn.execute(sql, params).fetchall()]

    def query_one(self, sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None
