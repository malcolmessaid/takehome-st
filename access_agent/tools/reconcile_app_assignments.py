from pydantic import BaseModel, Field

from access_agent.services.access_review_service import AccessReviewService
from access_agent.tools.base import Tool


class ReconcileAppAssignmentsArgs(BaseModel):
    application_name: str | None = Field(default=None, description="Limit to one application, e.g. 'Salesforce'. Omit for all applications.")
    sample_size: int = Field(default=20, ge=0, le=100, description="How many example pairs with no application row to return.")


def reconcile_app_assignments(args: ReconcileAppAssignmentsArgs) -> dict:
    return AccessReviewService().reconcile_app_assignments(args.application_name, args.sample_size)


TOOL = Tool(
    name="reconcile_app_assignments",
    description=(
        "Compare what IdP assignments grant (directly or through nested groups) with what each application reports in application_user_access. "
        "Returns coverage per application, pairs where the app reports non-active access despite a current assignment, and a sample of assigned "
        "accounts the app has no row for. Assignments are a partial export (e.g. VPN and AWS have none), so only use this for apps that have assignments."
    ),
    args_model=ReconcileAppAssignmentsArgs,
    fn=reconcile_app_assignments,
)
