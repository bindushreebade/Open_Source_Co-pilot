import os

from github import Github
from github.GithubException import GithubException
from dotenv import load_dotenv


load_dotenv()


class GitHubClient:

    def __init__(self):
        token = os.getenv("GITHUB_TOKEN")

        if not token:
            raise ValueError("GITHUB_TOKEN is not set in .env")

        self.github = Github(token)

    def get_repository(self, owner: str, repo: str):
        """
        Get a GitHub repository.

        """

        try:
            print(f"GitHub lookup: owner={owner!r}, repo={repo!r}")
            return self.github.get_repo(f"{owner}/{repo}")
        except GithubException as e:
            raise Exception(f"Could not get repository: {e}")
    

    def get_issue(self, owner: str, repo: str, issue_number: int):
        """
        Get a GitHub issue.
        """
        repository = self.get_repository(owner, repo)

        try:
            issue = repository.get_issue(number=issue_number)

            return {
                "number": issue.number,
                "title": issue.title,
                "body": issue.body,
                "state": issue.state,
                "url": issue.html_url,
                "user": issue.user.login if issue.user else None
            }

        except GithubException as e:
            raise Exception(f"Could not get issue: {e}")

    def get_issue_comments(
        self,
        owner: str,
        repo: str,
        issue_number: int
    ):
        """
        Get all comments associated with an issue.
        """
        repository = self.get_repository(owner, repo)

        try:
            issue = repository.get_issue(number=issue_number)

            comments = []

            for comment in issue.get_comments():
                comments.append({
                    "user": comment.user.login if comment.user else None,
                    "body": comment.body,
                    "created_at": str(comment.created_at),
                    "url": comment.html_url
                })

            return comments

        except GithubException as e:
            raise Exception(f"Could not get issue comments: {e}")

    def get_file(
        self,
        owner: str,
        repo: str,
        path: str,
        branch: str = None
    ):
        """
        Get the contents of a file from a repository.
        """
        repository = self.get_repository(owner, repo)

        try:
            if branch:
                file = repository.get_contents(path, ref=branch)
            else:
                file = repository.get_contents(path)

            if isinstance(file, list):
                raise Exception(f"{path} is a directory, not a file")

            content = file.decoded_content.decode("utf-8")

            return {
                "path": file.path,
                "content": content,
                "sha": file.sha,
                "url": file.html_url
            }

        except GithubException as e:
            raise Exception(f"Could not get file: {e}")

    def list_files(
        self,
        owner: str,
        repo: str,
        path: str = "",
        branch: str = None
    ):
        """
        List files/directories in a repository path.
        """
        repository = self.get_repository(owner, repo)

        try:
            if branch:
                contents = repository.get_contents(path, ref=branch)
            else:
                contents = repository.get_contents(path)

            if not isinstance(contents, list):
                contents = [contents]

            files = []

            for item in contents:
                files.append({
                    "name": item.name,
                    "path": item.path,
                    "type": item.type,
                    "size": item.size
                })

            return files

        except GithubException as e:
            raise Exception(f"Could not list files: {e}")