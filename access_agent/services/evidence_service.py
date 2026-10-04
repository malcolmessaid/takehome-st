import re

from access_agent.logger import get_logger
from access_agent.models.report import InvestigationReport
from access_agent.repos.evidence_repo import ID_TABLES, EvidenceRepo

logger = get_logger(__name__)

MAX_IDS = 120
MAX_VALUE_CHARS = 300
ID_PATTERN = re.compile(r"\b(?:" + "|".join(sorted(ID_TABLES, key=len, reverse=True)) + r")_\d+\b")
LABEL_FIELDS = ("full_name", "name", "login", "username", "primary_email", "application_name", "event_type")
STATE_FIELDS = ("status", "employment_status", "end_date", "sensitivity", "classification", "permission", "role", "occurred_at")

VERIFY_INSTRUCTIONS = """Before this report is accepted, check it against the records below. They are the actual database rows for every ID you cited, plus short labels for the records they point to.
For each finding:
- Confirm each cited record says what the statement claims: names, dates, statuses, counts, and who did what.
- Remove IDs that don't support the finding. IDs under not_found do not exist; remove them.
- Fix any fact the records contradict. If the records only suggest the conclusion, change kind to inference.
- Drop a finding if none of its records support it.
Then call submit_report again with the corrected report. If everything checks out, resubmit it unchanged."""


def _compact(row: dict) -> dict:
    return {k: (v[:MAX_VALUE_CHARS] + "..." if isinstance(v, str) and len(v) > MAX_VALUE_CHARS else v) for k, v in row.items() if v is not None}


def _label(row: dict) -> str:
    name = next((str(row[f]) for f in LABEL_FIELDS if row.get(f)), row["table"])
    state = ", ".join(f"{f}={row[f]}" for f in STATE_FIELDS if row.get(f))
    return f"{name} ({state})" if state else name


class EvidenceService:
    """Fetches the records behind a report's evidence IDs so the model can check its own claims against the data."""

    def __init__(self):
        self.repo = EvidenceRepo()

    def cited_ids(self, report: InvestigationReport) -> list[str]:
        return list(dict.fromkeys(i for f in report.findings for i in f.evidence_ids))

    def build_verification(self, report: InvestigationReport) -> dict:
        """Per finding: the statement, each cited record, labels for records it references, and any IDs that don't exist."""
        ids = self.cited_ids(report)[:MAX_IDS]
        records = self.repo.get_records(ids)
        referenced = {m for r in records.values() for v in r.values() if isinstance(v, str) for m in ID_PATTERN.findall(v)} - set(records)
        labels = {rid: _label(row) for rid, row in self.repo.get_records(list(referenced)).items()}
        findings = []
        for n, f in enumerate(report.findings, 1):
            evidence = []
            for rid in f.evidence_ids:
                if rid in records:
                    row = records[rid]
                    refs = {m: labels[m] for v in row.values() if isinstance(v, str) for m in ID_PATTERN.findall(v) if m in labels}
                    evidence.append({"id": rid, "record": _compact(row), "references": refs})
            findings.append({"finding": n, "statement": f.statement, "kind": f.kind, "evidence": evidence, "not_found": [i for i in f.evidence_ids if i not in records]})
        not_found = [i for i in ids if i not in records]
        logger.info(f"Built evidence verification id_count={len(ids)} found_count={len(records)} not_found_count={len(not_found)}")
        return {"status": "verification_required", "instructions": VERIFY_INSTRUCTIONS, "ids_checked": len(ids), "not_found": not_found, "findings": findings}

    def summarize(self, draft: InvestigationReport, final: InvestigationReport) -> dict:
        """What the check changed, plus a final existence check on the IDs the corrected report cites."""
        draft_ids, final_ids = self.cited_ids(draft), self.cited_ids(final)
        found = self.repo.get_records(draft_ids + final_ids)
        draft_findings = {(f.statement, f.kind, tuple(f.evidence_ids)) for f in draft.findings}
        return {
            "ids_checked": len(draft_ids),
            "ids_not_found_in_draft": [i for i in draft_ids if i not in found],
            "ids_not_found_in_final": [i for i in final_ids if i not in found],
            "findings_changed": sum(1 for f in final.findings if (f.statement, f.kind, tuple(f.evidence_ids)) not in draft_findings),
            "findings_dropped": max(0, len(draft.findings) - len(final.findings)),
            "revised": draft.model_dump(exclude={"verification"}) != final.model_dump(exclude={"verification"}),
        }
