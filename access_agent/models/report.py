from enum import StrEnum

from pydantic import BaseModel, Field


class FindingKind(StrEnum):
    FACT = "fact"
    INFERENCE = "inference"


class Finding(BaseModel):
    """One conclusion from the investigation."""

    statement: str = Field(description="The conclusion in one or two plain sentences.")
    kind: FindingKind = Field(description="fact: directly shown by the cited records. inference: your interpretation of them.")
    evidence_ids: list[str] = Field(description="Record or event IDs that support this finding, e.g. evt_00000001, acc_000123, per_000019.")


class InvestigationReport(BaseModel):
    """The final answer to an access investigation."""

    summary: str = Field(description="Two or three sentence answer to the question.")
    findings: list[Finding] = Field(description="Facts and inferences, each with supporting IDs.")
    data_gaps: list[str] = Field(description="Missing, incomplete, or contradictory data that limits the conclusions.")
    recommended_actions: list[str] = Field(description="Suggested next steps for a human. Never claim to have taken them.")
