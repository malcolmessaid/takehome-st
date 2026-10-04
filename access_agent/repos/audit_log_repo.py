from access_agent.db import Database
from access_agent.models.audit_log import AuditEvent


class AuditLogRepo:
    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def get_first_event(self) -> AuditEvent | None:
        row = self.db.query_one("SELECT * FROM audit_events LIMIT 1")
        return AuditEvent(**row) if row else None

    def get_events_by_actors_after(self, actor_ids: list[str], after: str, limit: int = 10) -> tuple[list[AuditEvent], int]:
        """Events initiated by any of the actor IDs after a timestamp, newest first, and the total count."""
        if not actor_ids:
            return [], 0
        placeholders = ", ".join("?" for _ in actor_ids)
        where = f"WHERE actor_id IN ({placeholders}) AND occurred_at > ?"
        total = self.db.query_one(f"SELECT COUNT(*) AS n FROM audit_events {where}", (*actor_ids, after))["n"]
        rows = self.db.query(f"SELECT * FROM audit_events {where} ORDER BY occurred_at DESC LIMIT ?", (*actor_ids, after, limit))
        return [AuditEvent(**r) for r in rows], total

    def get_lifecycle_events(self, target_ids: list[str]) -> list[AuditEvent]:
        """HR events, lifecycle evaluations, failures, and access exceptions targeting any of the IDs, oldest first."""
        if not target_ids:
            return []
        placeholders = ", ".join("?" for _ in target_ids)
        sql = f"""
            SELECT * FROM audit_events
            WHERE target_id IN ({placeholders}) AND event_type != 'worker.record.updated'
              AND (system = 'hr' OR event_type LIKE 'lifecycle.%' OR event_type LIKE '%.failed' OR event_type LIKE 'access.exception.%')
            ORDER BY occurred_at
        """
        return [AuditEvent(**r) for r in self.db.query(sql, tuple(target_ids))]
