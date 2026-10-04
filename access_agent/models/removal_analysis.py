from enum import StrEnum

from pydantic import BaseModel, Field


class CheckStatus(StrEnum):
    FAIL = "fail"
    PASS = "pass"
    INFO = "info"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Age(StrEnum):
    RECENT = "recent"
    LONG_STANDING = "long_standing"


SEVERITY_ORDER = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]


class RemovalCheck(BaseModel):
    """One offboarding check for a removed person."""

    system: str = Field(description="hr, idp, workspace, github, mdm, or audit.")
    check: str = Field(description="Short name of what was checked, e.g. idp_account_disabled.")
    status: CheckStatus = Field(description="fail: access or activity remains. pass: removed as expected. info: context, e.g. offboarding events.")
    severity: Severity = Field(description="How serious a failure is. Passing checks are info.")
    detail: str = Field(description="Plain-language explanation of the result.")
    days_after_end: int | None = Field(description="Days between end_date and the snapshot (leftover access), the latest activity, or the late removal.")
    age: Age | None = Field(description="recent or long_standing, from days_after_end.")
    evidence_ids: list[str] = Field(description="Record or event IDs behind this result.")


class RemovalAnalysis(BaseModel):
    """Whether one removed person's access was actually taken away, as of the snapshot."""

    person_id: str
    full_name: str
    worker_type: str
    employment_status: str
    end_date: str | None
    snapshot_at: str
    days_since_end: int | None = Field(description="Days from end_date to the snapshot.")
    highest_severity: Severity = Field(description="Most serious failing check, or info if nothing failed.")
    failed_checks: int
    checks: list[RemovalCheck]
