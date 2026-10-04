import os
from pathlib import Path

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage

from access_agent.logger import get_logger

logger = get_logger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-5.6-luna"
TOKEN_FILE = Path(__file__).resolve().parent.parent / "token.txt"


def load_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    raise RuntimeError("Set OPENROUTER_API_KEY or put the key in token.txt (gitignored).")


class LLMClient:
    """Thin wrapper around OpenRouter's OpenAI-compatible chat API."""

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
        self.client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=load_api_key())

    def run(self, messages: list[dict], tools: list[dict] | None = None) -> ChatCompletionMessage:
        logger.info(f"Calling LLM model={self.model} message_count={len(messages)} tool_count={len(tools or [])}")
        kwargs = {"tools": tools} if tools else {}
        response = self.client.chat.completions.create(model=self.model, messages=messages, **kwargs)
        return response.choices[0].message
