import argparse
import readline  # noqa: F401  enables arrow keys and line editing in input()

from access_agent.agent_service import AgentService
from access_agent.logger import Verbosity, configure_logging
from access_agent.models.report import InvestigationReport


def print_report(report: InvestigationReport) -> None:
    print(f"\nSUMMARY\n  {report.summary}")
    print("\nFINDINGS")
    for f in report.findings:
        print(f"  [{f.kind}] {f.statement}\n      evidence: {', '.join(f.evidence_ids) or 'none'}")
    print("\nDATA GAPS")
    for gap in report.data_gaps:
        print(f"  - {gap}")
    print("\nRECOMMENDED ACTIONS")
    for action in report.recommended_actions:
        print(f"  - {action}")


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
    args = parser.parse_args()
    configure_logging(args.verbosity)
    agent = AgentService()
    print(f"Access investigation agent ({agent.llm.model}, verbosity={args.verbosity}). Type 'exit', press Ctrl-C, or Ctrl-D to quit.")
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
    except (EOFError, KeyboardInterrupt):
        print()


if __name__ == "__main__":
    main()
