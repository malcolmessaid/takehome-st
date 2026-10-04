from access_agent.llm_client import LLMClient
from access_agent.logger import get_logger
from access_agent.models.report import InvestigationReport
from access_agent.repos.people_repo import PeopleRepo
from access_agent.tools import SUBMIT_REPORT, TOOLS, execute_tool

logger = get_logger(__name__)

MAX_STEPS = 15

SYSTEM_PROMPT = """You are an access investigation assistant for a security team. You investigate employee access using read-only tools over a snapshot of HR, identity provider (IdP), Google Workspace, GitHub, device, and audit data.

Snapshot time: {snapshot_at}. Treat this as "now".

Rules:
- Every conclusion must cite the record or event IDs that support it. Never invent IDs.
- Separate facts (directly shown by records) from inferences (your interpretation).
- Systems can disagree: HR employment_status, account status, and application access status are tracked separately.
- A relationship is current only if revoked_at IS NULL and expires_at (if present) is after the snapshot time.
- Groups can nest; IDs in member_id, principal_id, actor_id, and target_id must be read with their *_type column.
- A NULL person_id means the record couldn't be matched to a person, not that it is bad data.
- Audit logs are incomplete. An event can prove an action happened without proving which human caused it.
- You may recommend actions but never claim to have changed anything.
- If the question is ambiguous (e.g. several people match a name), ask the user instead of guessing.
- For simple lookups (e.g. "who is in the system"), answer directly in text. For investigations, finish by calling submit_report exactly once."""


class AgentService:
    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient()
        self.tool_schemas = [t.schema() for t in TOOLS.values()]
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT.format(snapshot_at=PeopleRepo().get_snapshot_time())}]

    def run(self, user_message: str) -> InvestigationReport | str:
        """Runs the tool loop for one user turn. Returns a report, or plain text if the model replies without a report."""
        self.messages.append({"role": "user", "content": user_message})
        for step in range(MAX_STEPS):
            msg = self.llm.run(self.messages, tools=self.tool_schemas)
            if not msg.tool_calls:
                self.messages.append({"role": "assistant", "content": msg.content or ""})
                return msg.content or ""
            self.messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
            report = None
            for call in msg.tool_calls:
                if call.function.name == SUBMIT_REPORT:
                    logger.info(f"Tool call step={step} tool_name={call.function.name}")
                    report = InvestigationReport.model_validate_json(call.function.arguments)
                    result = '{"status": "report received"}'
                else:
                    result = execute_tool(call.function.name, call.function.arguments)
                    logger.info(f"Tool call step={step} tool_name={call.function.name} arguments={call.function.arguments} result_chars={len(result)}")
                self.messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
            if report is not None:
                return report
        logger.info(f"Agent hit step limit max_steps={MAX_STEPS}")
        return f"Stopped after {MAX_STEPS} steps without a final report."
