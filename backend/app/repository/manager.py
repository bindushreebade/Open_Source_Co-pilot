import os
from git import Repo


class RepositoryManager:

    def __init__(self):
        # Project root = open-source-copilot
        self.project_root = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "../../../"
            )
        )

        self.repositories_path = os.path.join(
            self.project_root,
            "repositories"
        )

        os.makedirs(
            self.repositories_path,
            exist_ok=True
        )

    def clone_repository(self, repository_url: str):

        # Extract repository name
        repository_name = repository_url.rstrip("/").split("/")[-1]

        if repository_name.endswith(".git"):
            repository_name = repository_name[:-4]

        repository_path = os.path.join(
            self.repositories_path,
            repository_name
        )

        # Don't clone if already exists
        if os.path.exists(repository_path):
            return {
                "message": "Repository already exists",
                "path": repository_path
            }

        # Clone repository
        Repo.clone_from(
            repository_url,
            repository_path
        )

        return {
            "message": "Repository cloned successfully",
            "path": repository_path
        }

    def list_files(self, repository_path: str):

        files = []

        for root, directories, filenames in os.walk(
            repository_path
        ):

            # Ignore .git directory
            directories[:] = [
                d for d in directories
                if d != ".git"
            ]

            for filename in filenames:

                full_path = os.path.join(
                    root,
                    filename
                )

                relative_path = os.path.relpath(
                    full_path,
                    repository_path
                )

                files.append(
                    relative_path
                )

        return files

    def read_file(
        self,
        repository_path: str,
        file_path: str
    ):

        full_path = os.path.join(
            repository_path,
            file_path
        )

        # Security check
        full_path = os.path.abspath(full_path)
        repository_path = os.path.abspath(repository_path)

        if not full_path.startswith(repository_path):
            raise ValueError(
                "Access outside repository is not allowed"
            )

        if not os.path.isfile(full_path):
            raise FileNotFoundError(
                f"File not found: {file_path}"
            )

        with open(
            full_path,
            "r",
            encoding="utf-8"
        ) as file:

            return file.read()