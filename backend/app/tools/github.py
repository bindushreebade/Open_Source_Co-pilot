import os

from github import Github
from github import GithubException
from dotenv import load_dotenv


load_dotenv()


class GitHubTools:

    def __init__(self):
        token = os.getenv("GITHUB_TOKEN")

        if not token:
            raise RuntimeError(
                "GITHUB_TOKEN is not set in the .env file."
            )

        self.github = Github(token)

    def get_repository(self, owner: str, repo: str):
        try:
            return self.github.get_repo(
                f"{owner}/{repo}"
            )

        except GithubException as e:
            raise RuntimeError(
                f"Could not access GitHub repository "
                f"{owner}/{repo}: {e}"
            )

    def get_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int
    ):
        try:
            repository = self.get_repository(
                owner,
                repo
            )

            issue = repository.get_issue(
                number=issue_number
            )

            return {
                "success": True,
                "number": issue.number,
                "title": issue.title,
                "body": issue.body or "",
                "state": issue.state,
                "url": issue.html_url,
                "user": (
                    issue.user.login
                    if issue.user
                    else None
                ),
            }

        except GithubException as e:

            return {
                "success": False,
                "error": str(e)
            }

        except Exception as e:

            return {
                "success": False,
                "error": str(e)
            }

    def get_default_branch(
        self,
        owner: str,
        repo: str
    ):

        try:

            repository = self.get_repository(
                owner,
                repo
            )

            return repository.default_branch

        except Exception as e:

            raise RuntimeError(
                f"Could not determine default branch: {e}"
            )


github_tools = GitHubTools()


def get_issue(
    owner: str,
    repo: str,
    issue_number: int
):
    return github_tools.get_issue(
        owner,
        repo,
        issue_number
    )