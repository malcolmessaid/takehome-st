from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel


@dataclass(frozen=True)
class Tool:
    """A function the model can call. args_model defines and validates its arguments."""

    name: str
    description: str
    args_model: type[BaseModel]
    fn: Callable[[Any], Any] | None = None

    def schema(self) -> dict:
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.args_model.model_json_schema()}}
