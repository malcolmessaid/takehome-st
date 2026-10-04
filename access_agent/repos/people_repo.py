from access_agent.db import Database
from access_agent.models.devices import Device
from access_agent.models.people import Person


class PeopleRepo:
    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def get_snapshot_time(self) -> str:
        return self.db.query_one("SELECT value FROM dataset_metadata WHERE key = 'snapshot_at'")["value"]

    def find_people(self, query: str, limit: int = 10) -> list[Person]:
        """People whose name or email contains the query, or whose person_id matches it exactly."""
        pattern = f"%{query}%"
        rows = self.db.query("SELECT * FROM people WHERE full_name LIKE ? OR primary_email LIKE ? OR person_id = ? ORDER BY full_name LIMIT ?", (pattern, pattern, query, limit))
        return [Person(**r) for r in rows]

    def list_people(self, employment_status: str | None = None, worker_type: str | None = None, department: str | None = None, limit: int = 25, offset: int = 0) -> tuple[list[Person], int]:
        """A page of people matching the filters, and the total number that matched."""
        filters = {"employment_status = :employment_status": employment_status, "worker_type = :worker_type": worker_type, "department = :department": department}
        clauses = [clause for clause, value in filters.items() if value is not None]
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params = {"employment_status": employment_status, "worker_type": worker_type, "department": department, "limit": limit, "offset": offset}
        total = self.db.query_one(f"SELECT COUNT(*) AS n FROM people {where}", params)["n"]
        rows = self.db.query(f"SELECT * FROM people {where} ORDER BY full_name LIMIT :limit OFFSET :offset", params)
        return [Person(**r) for r in rows], total

    def get_people_counts(self) -> list[dict]:
        return self.db.query("SELECT employment_status, worker_type, COUNT(*) AS people FROM people GROUP BY 1, 2 ORDER BY 1, 2")

    def get_departments(self) -> list[str]:
        return [r["department"] for r in self.db.query("SELECT DISTINCT department FROM people ORDER BY 1")]

    def list_removed_people(self, snapshot_date: str, since_date: str | None = None) -> list[Person]:
        """People marked ended, plus anyone whose end_date has passed without being marked ended. since_date filters on end_date."""
        sql = """
            SELECT * FROM people
            WHERE (employment_status = 'ended' OR (end_date IS NOT NULL AND end_date <= :snapshot_date))
              AND (:since_date IS NULL OR end_date >= :since_date)
            ORDER BY end_date DESC
        """
        return [Person(**r) for r in self.db.query(sql, {"snapshot_date": snapshot_date, "since_date": since_date})]

    def get_people_with_end_before_start(self) -> list[Person]:
        return [Person(**r) for r in self.db.query("SELECT * FROM people WHERE end_date < start_date ORDER BY person_id")]

    def get_person(self, person_id: str) -> Person | None:
        row = self.db.query_one("SELECT * FROM people WHERE person_id = ?", (person_id,))
        return Person(**row) if row else None

    def get_devices_for_person(self, person_id: str) -> list[Device]:
        return [Device(**r) for r in self.db.query("SELECT * FROM devices WHERE person_id = ?", (person_id,))]
