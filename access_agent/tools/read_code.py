from pathlib import Path

from pydantic import BaseModel, Field

from access_agent.tools.base import Tool

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
READABLE_PATHS = ["access_agent/**/*.py", "input_data/SCHEMA.md"]


def readable_files() -> list[str]:
    return sorted({str(p.relative_to(PROJECT_ROOT)) for pattern in READABLE_PATHS for p in PROJECT_ROOT.glob(pattern)})


class ReadCodeArgs(BaseModel):
    path: str | None = Field(default=None, description="Project-relative file path, e.g. access_agent/repos/identity_provider_repo.py. Omit to list readable files.")


def read_code(args: ReadCodeArgs) -> dict:
    files = readable_files()
    if args.path is None:
        return {"files": files}
    if args.path not in files:
        return {"error": f"Not readable: {args.path}", "files": files}
    return {"path": args.path, "content": (PROJECT_ROOT / args.path).read_text()}


TOOL = Tool(
    name="read_code",
    description="Read this project's source code, e.g. repos with tested SQL for nested groups, current-access rules, and removal checks. Omit path to list files.",
    args_model=ReadCodeArgs,
    fn=read_code,
)
