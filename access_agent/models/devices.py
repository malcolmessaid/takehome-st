from enum import StrEnum

from pydantic import BaseModel, Field


class DevicePlatform(StrEnum):
    MACOS = "macos"
    WINDOWS = "windows"
    LINUX = "linux"
    IOS = "ios"
    ANDROID = "android"


class DeviceOwnership(StrEnum):
    COMPANY = "company"
    PERSONAL = "personal"


class ComplianceStatus(StrEnum):
    COMPLIANT = "compliant"
    NONCOMPLIANT = "noncompliant"
    UNKNOWN = "unknown"


class Device(BaseModel):
    """A device known to device management (MDM). Linked to a person only through person_id, never to an account."""

    device_id: str = Field(description="Device identifier.")
    person_id: str | None = Field(description="HR person this device belongs to. NULL means it couldn't be confidently matched, not necessarily bad data.")
    serial_number: str = Field(description="Hardware serial number.")
    platform: DevicePlatform = Field(description="Operating system platform.")
    ownership: DeviceOwnership = Field(description="Company-owned or personal (BYOD).")
    compliance_status: ComplianceStatus = Field(description="Latest MDM compliance result.")
    enrolled_at: str = Field(description="When the device enrolled in MDM (UTC ISO 8601).")
    last_check_in_at: str | None = Field(description="Most recent MDM check-in (UTC ISO 8601).")
    retired_at: str | None = Field(description="When the device was retired. NULL means it is still in service.")
