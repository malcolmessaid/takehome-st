from enum import StrEnum

from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema


class FindingKind(StrEnum):
    FACT = "fact"
    INFERENCE = "inference"


class Finding(BaseModel):
    """One conclusion from the investigation."""

    title: str = Field(description="Short headline, under 8 words, e.g. 'IdP account still active'.")
    statement: str = Field(description="One plain sentence, under 30 words. Name the key items; don't list every app, group, or file.")
    kind: FindingKind = Field(description="fact: directly shown by the cited records. inference: your interpretation of them.")
    evidence_ids: list[str] = Field(description="Most important record or event IDs first, e.g. evt_00000001, acc_000123, per_000019.")


class InvestigationReport(BaseModel):
    """The final answer to an access investigation."""

    summary: str = Field(description="Lead with a direct answer (e.g. 'No, offboarding is incomplete.'), then one sentence on why. Under 40 words.")
    findings: list[Finding] = Field(description="At most 7 findings, most severe first. Group related items into one finding.")
    data_gaps: list[str] = Field(description="Missing, incomplete, or contradictory data that limits the conclusions. One short sentence each.")
    recommended_actions: list[str] = Field(description="Short imperative next steps for a human, most urgent first, at most 5. Never claim to have taken them.")
    verification: SkipJsonSchema[dict | None] = None
