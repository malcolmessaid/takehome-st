import sys

from access_agent.llm_client import LLMClient
from access_agent.repos.audit_log_repo import AuditLogRepo
from access_agent.repos.github_repo import GithubRepo
from access_agent.repos.google_workspace_repo import GoogleWorkspaceRepo
from access_agent.repos.identity_provider_repo import IdentityProviderRepo
from access_agent.services.person_access_service import PersonAccessService


def repos_main() -> None:
    print(IdentityProviderRepo().get_first_account())
    print(GoogleWorkspaceRepo().get_first_account())
    print(GithubRepo().get_first_account())
    print(AuditLogRepo().get_first_event())


def llm_main(prompt: str) -> None:
    print(LLMClient().run([{"role": "user", "content": prompt}]).content)


def person_main(query: str) -> None:
    service = PersonAccessService()
    matches = service.find_person(query)
    print(f"{len(matches)} match(es): {[(p.person_id, p.full_name) for p in matches]}")
    if len(matches) == 1:
        print(service.get_person_access(matches[0].person_id).model_dump_json(indent=2))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "llm":
        llm_main(" ".join(sys.argv[2:]) or "Say hello in one sentence.")
    elif command == "person":
        person_main(" ".join(sys.argv[2:]))
    else:
        repos_main()
