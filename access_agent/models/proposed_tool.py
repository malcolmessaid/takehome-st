from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

from access_agent.models.report import InvestigationReport


class ParameterType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    DATE = "date"
    TIMESTAMP = "timestamp"


class ToolParameter(BaseModel):
    name: str = Field(description="Matches a :name placeholder in the SQL, e.g. person_id.")
    type: ParameterType = Field(description="Value type. Dates are YYYY-MM-DD; timestamps are ISO 8601 UTC like the snapshot time.")
    description: str = Field(description="What the caller passes, e.g. 'person_id of the person who left'.")


class ProposedTool(BaseModel):
    """A reusable tool generalized from SQL that produced evidence in this investigation."""

    name: str = Field(description="snake_case tool name, e.g. get_leftover_github_grants.")
    description: str = Field(description="When a model should call this tool and what it returns, in one or two sentences.")
    parameters: list[ToolParameter] = Field(description="One entry per :name placeholder in the SQL.")
    sql: str = Field(description="One read-only SELECT using :name placeholders instead of hardcoded IDs or dates. Must return the ID columns a report would cite.")
    example_args: dict[str, Any] = Field(description="Arguments that reproduce this investigation's evidence, e.g. {\"person_id\": \"per_001942\"}.")
    supports_findings: list[int] = Field(description="1-based numbers of the findings this tool's output supports.")
    validation: SkipJsonSchema[str | None] = None


class SqlInvestigationReport(InvestigationReport):
    """The final report from the SQL agent, plus tools proposed from the queries it ran."""

    proposed_tools: list[ProposedTool] = Field(description="1 to 5 reusable tools that would let a future agent reach the same findings without writing SQL.")
