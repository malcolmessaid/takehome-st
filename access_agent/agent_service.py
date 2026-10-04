import json

from access_agent.llm_client import LLMClient
from access_agent.logger import get_logger
from access_agent.models.report import InvestigationReport
from access_agent.repos.people_repo import PeopleRepo
from access_agent.services.evidence_service import EvidenceService
from access_agent.tools.base import Tool
from access_agent.tools.registry import TOOLS, execute_tool
from access_agent.tools.submit_report import SUBMIT_REPORT

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
- For simple lookups (e.g. "who is in the system"), answer directly in text. For investigations, finish by calling submit_report exactly once.
- Write reports for a busy human reviewer: short plain sentences, no jargon like "materially". Summarize lists (e.g. "6 apps including VPN and GitHub") instead of enumerating them."""


def _parse_json(raw: str | None) -> dict:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"unparsed": raw}


TOOL_PLAYBOOKS = """

Playbooks. Prefer one company-wide tool over looping a per-person tool, and call independent tools in the same step.
- What can someone access: find_person -> get_person_access.
- Did one person leave properly: find_person -> analyze_removal.
- Did everyone who left lose access: list_removed_people -> analyze_removal for the most recent or highest-risk people; get_leftover_direct_grants for the company-wide sweep of direct grants; find_unlinked_accounts for accounts no offboarding covers.
- Anything suspicious / what changed: find_change_events -> get_activity_timeline(around_event_id) on flagged events -> get_person_access for the people involved.
- Privileged access review: find_privileged_access, then find_change_events for how recent grants were made.
- Third-party app risk: find_risky_oauth_grants. MFA: find_mfa_gaps. IdP vs application provisioning: reconcile_app_assignments.
- Data quality and timing (impossible dates, activity before an account existed, grants after leaving): find_lifecycle_anomalies. Check it before trusting "days since leaving" for a person whose dates look odd."""


class AgentService:
    def __init__(self, llm: LLMClient | None = None, tools: dict[str, Tool] = TOOLS, system_prompt: str | None = None, max_steps: int = MAX_STEPS, verify_evidence: bool = True):
        self.llm = llm or LLMClient()
        self.tools = tools
        self.max_steps = max_steps
        self.verify_evidence = verify_evidence
        self.evidence = EvidenceService()
        self.tool_schemas = [t.schema() for t in tools.values()]
        self.messages: list[dict] = [{"role": "system", "content": system_prompt or SYSTEM_PROMPT.format(snapshot_at=PeopleRepo().get_snapshot_time()) + TOOL_PLAYBOOKS}]
        self.trace: list[dict] = []

    def run(self, user_message: str) -> InvestigationReport | str:
        """Runs the tool loop for one user turn. Returns a report, or plain text if the model replies without a report.

        With verify_evidence, the first submit_report is treated as a draft: the records behind every cited ID are sent back and the model
        must check its findings against them and resubmit. The final report's verification field records what the check changed.
        self.trace holds this turn's tool calls (step, tool name, arguments, result size, error) for later inspection.
        """
        self.messages.append({"role": "user", "content": user_message})
        self.trace = []
        draft = None
        for step in range(self.max_steps):
            msg = self.llm.run(self.messages, tools=self.tool_schemas)
            if not msg.tool_calls:
                self.messages.append({"role": "assistant", "content": msg.content or ""})
                if draft is not None:
                    draft.verification = {"incomplete": "model replied without resubmitting after the evidence check"}
                    return draft
                return msg.content or ""
            self.messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
            report = None
            for call in msg.tool_calls:
                if call.function.name == SUBMIT_REPORT:
                    submitted = self.tools[SUBMIT_REPORT].args_model.model_validate_json(call.function.arguments)
                    if self.verify_evidence and draft is None:
                        draft = submitted
                        verification = self.evidence.build_verification(submitted)
                        result = json.dumps(verification, default=str)
                        logger.info(f"Tool call step={step} tool_name={call.function.name} evidence_check=requested ids_checked={verification['ids_checked']} not_found_count={len(verification['not_found'])}")
                    else:
                        report = submitted
                        if draft is not None:
                            report.verification = self.evidence.summarize(draft, report)
                        logger.info(f"Tool call step={step} tool_name={call.function.name} evidence_check={'done' if draft is not None else 'off'}")
                        result = '{"status": "report received"}'
                else:
                    result = execute_tool(call.function.name, call.function.arguments, self.tools)
                    logger.info(f"Tool call step={step} tool_name={call.function.name} arguments={call.function.arguments} result_chars={len(result)}")
                    self.trace.append({"step": step, "tool": call.function.name, "arguments": _parse_json(call.function.arguments), "result_chars": len(result), "error": json.loads(result).get("error") if result.startswith('{"error"') else None})
                self.messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
            if report is not None:
                return report
        logger.info(f"Agent hit step limit max_steps={self.max_steps}")
        if draft is not None:
            draft.verification = {"incomplete": f"hit the {self.max_steps}-step limit during the evidence check"}
            return draft
        return f"Stopped after {self.max_steps} steps without a final report."
