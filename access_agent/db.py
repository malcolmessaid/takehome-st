import os
import sqlite3
import time
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "input_data" / "access_snapshot.sqlite"
QUERY_TIMEOUT_SECONDS = 10
ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}


def _authorize(action: int, *_: Any) -> int:
    """Allows only reads. Writes, schema changes, PRAGMA, ATTACH, and transactions are denied at prepare time."""
    return sqlite3.SQLITE_OK if action in ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


class Database:
    """Read-only singleton connection to the access snapshot.

    SQLite has no users or grants, so read-only is enforced in layers:
    1. The file is opened with mode=ro, so SQLite refuses to write to it.
    2. PRAGMA query_only blocks writes even if the open mode were changed.
    3. An authorizer denies every statement type except SELECT (this also blocks PRAGMA, ATTACH, and temp tables).
    4. A progress handler aborts queries that run longer than QUERY_TIMEOUT_SECONDS.
    """

    _instance: "Database | None" = None

    def __new__(cls) -> "Database":
        if cls._instance is None:
            db_path = Path(os.environ.get("ACCESS_DB_PATH", DEFAULT_DB_PATH))
            instance = super().__new__(cls)
            instance.conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
            instance.conn.row_factory = sqlite3.Row
            instance.conn.execute("PRAGMA query_only = ON")
            instance.conn.set_authorizer(_authorize)
            cls._instance = instance
        return cls._instance

    def _execute(self, sql: str, params: tuple | dict) -> sqlite3.Cursor:
        deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS
        self.conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
        return self.conn.execute(sql, params)

    def query(self, sql: str, params: tuple | dict = (), max_rows: int | None = None) -> list[dict[str, Any]]:
        cursor = self._execute(sql, params)
        rows = cursor.fetchall() if max_rows is None else cursor.fetchmany(max_rows)
        return [dict(row) for row in rows]

    def query_one(self, sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
        row = self._execute(sql, params).fetchone()
        return dict(row) if row else None
