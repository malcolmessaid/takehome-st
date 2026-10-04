from enum import StrEnum

from pydantic import BaseModel, Field


class WorkerType(StrEnum):
    EMPLOYEE = "employee"
    CONTRACTOR = "contractor"


class EmploymentStatus(StrEnum):
    ACTIVE = "active"
    ENDED = "ended"
    LEAVE = "leave"
    PREHIRE = "prehire"


class Person(BaseModel):
    """An HR roster entry. person_id is the shared identifier that links accounts and devices across systems."""

    person_id: str = Field(description="Shared HR person identifier, e.g. per_000001.")
    full_name: str = Field(description="Person's full name.")
    primary_email: str = Field(description="Primary corporate email address.")
    worker_type: WorkerType = Field(description="Employee or contractor.")
    department: str = Field(description="HR department.")
    title: str = Field(description="Job title.")
    manager_person_id: str | None = Field(description="person_id of this person's manager, if known.")
    employment_status: EmploymentStatus = Field(description="HR employment state. Can disagree with account statuses in other systems.")
    start_date: str = Field(description="Employment start date (YYYY-MM-DD).")
    end_date: str | None = Field(description="Employment end date (YYYY-MM-DD), if employment has ended or is scheduled to end.")
    location: str = Field(description="Work location.")


class DatasetMetadata(BaseModel):
    """Key/value metadata about the snapshot, including the snapshot timestamp."""

    key: str = Field(description="Metadata key, e.g. snapshot_at.")
    value: str = Field(description="Metadata value.")
