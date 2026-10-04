from access_agent.db import Database
from access_agent.models.audit_log import AuditEvent


class AuditLogRepo:
    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def get_first_event(self) -> AuditEvent | None:
        row = self.db.query_one("SELECT * FROM audit_events LIMIT 1")
        return AuditEvent(**row) if row else None
