import argparse
import readline  # noqa: F401  enables arrow keys and line editing in input()
import shutil
import textwrap

from access_agent.agent_service import AgentService
from access_agent.logger import Verbosity, configure_logging
from access_agent.models.proposed_tool import SqlInvestigationReport
from access_agent.models.report import InvestigationReport
from access_agent.sql_agent_service import SqlAgentService


BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
MAX_EVIDENCE_SHOWN = 6


def wrap(text: str, indent: str, first_indent: str | None = None) -> str:
    width = min(shutil.get_terminal_size().columns, 110)
    return textwrap.fill(text, width=width, initial_indent=first_indent if first_indent is not None else indent, subsequent_indent=indent)


def format_evidence(ids: list[str]) -> str:
    shown = ", ".join(ids[:MAX_EVIDENCE_SHOWN]) or "none"
    return f"{shown} +{len(ids) - MAX_EVIDENCE_SHOWN} more" if len(ids) > MAX_EVIDENCE_SHOWN else shown


def print_report(report: InvestigationReport) -> None:
    print(f"\n{BOLD}SUMMARY{RESET}\n{wrap(report.summary, '  ')}")
    print(f"\n{BOLD}FINDINGS{RESET}")
    for i, f in enumerate(report.findings, 1):
        label = "" if f.kind == "fact" else " (inference)"
        print(f"\n  {i}. {BOLD}{f.title}{RESET}{label}\n{wrap(f.statement, '     ')}")
        print(f"{DIM}{wrap(format_evidence(f.evidence_ids), '               ', '     evidence: ')}{RESET}")
    print(f"\n{BOLD}DATA GAPS{RESET}")
    for gap in report.data_gaps:
        print(wrap(gap, "    ", "  - "))
    print(f"\n{BOLD}RECOMMENDED ACTIONS{RESET}")
    for i, action in enumerate(report.recommended_actions, 1):
        print(wrap(action, "     ", f"  {i}. "))


def print_proposed_tools(report: SqlInvestigationReport) -> None:
    print(f"\n{BOLD}PROPOSED TOOLS{RESET}")
    for i, tool in enumerate(report.proposed_tools, 1):
        params = ", ".join(f"{p.name}: {p.type}" for p in tool.parameters)
        print(f"\n  {i}. {BOLD}{tool.name}{RESET}({params})  [{tool.validation}]\n{wrap(tool.description, '     ')}")
        print(f"{DIM}     supports findings: {', '.join(map(str, tool.supports_findings)) or 'none'}{RESET}")


def print_credit(agent: AgentService) -> None:
    try:
        remaining, limit = agent.llm.get_credit_remaining()
    except Exception as e:
        print(f"OpenRouter credit: unavailable ({type(e).__name__})")
        return
    print("OpenRouter credit: no spending limit on this key" if limit is None else f"OpenRouter credit: ${remaining:.2f} of ${limit:.2f} remaining")


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive access investigation agent.")
    parser.add_argument("--verbosity", type=Verbosity, choices=list(Verbosity), default=Verbosity.CLEAN, help="clean: no logs. mini: tool-call logs only. verbose: all logs.")
    parser.add_argument("--agent", choices=["tools", "sql"], default="tools", help="tools: purpose-built tools. sql: the model writes its own read-only SQL.")
    args = parser.parse_args()
    configure_logging(args.verbosity)
    agent = SqlAgentService() if args.agent == "sql" else AgentService()
    print(f"Access investigation agent ({args.agent}, {agent.llm.model}, verbosity={args.verbosity}). Type 'exit', press Ctrl-C, or Ctrl-D to quit.")
    print_credit(agent)
    try:
        while True:
            user_input = input("\nyou> ").strip()
            if user_input.lower() in ("exit", "quit"):
                break
            if not user_input:
                continue
            result = agent.run(user_input)
            if isinstance(result, InvestigationReport):
                print_report(result)
            else:
                print(f"\nagent> {result}")
            if isinstance(result, SqlInvestigationReport):
                print_proposed_tools(result)
            if isinstance(agent, SqlAgentService) and agent.last_run_path:
                print(f"\n{DIM}Queries and report saved to {agent.last_run_path}{RESET}")
    except (EOFError, KeyboardInterrupt):
        print()


if __name__ == "__main__":
    main()
