import os
from pathlib import Path


def _safe_path(
    repository_path: str,
    file_path: str
) -> Path:

    repository = Path(
        repository_path
    ).resolve()

    target = (
        repository / file_path
    ).resolve()

    try:
        target.relative_to(repository)

    except ValueError:

        raise ValueError(
            "File path escapes the repository."
        )

    return target


def read_file(
    repository_path: str,
    file_path: str,
    line_start: int | None = None,
    line_end: int | None = None
):

    try:

        target = _safe_path(
            repository_path,
            file_path
        )

        if not target.exists():

            return {
                "success": False,
                "error": (
                    f"File not found: {file_path}"
                )
            }

        if not target.is_file():

            return {
                "success": False,
                "error": (
                    f"Not a file: {file_path}"
                )
            }

        text = target.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        lines = text.splitlines()

        # Return complete file
        if line_start is None:

            return {
                "success": True,
                "path": file_path,
                "content": text
            }

        start = max(
            1,
            line_start
        )

        end = (
            line_end
            if line_end is not None
            else len(lines)
        )

        selected = lines[
            start - 1:end
        ]

        numbered = []

        for index, line in enumerate(
            selected,
            start=start
        ):

            numbered.append(
                f"{index}: {line}"
            )

        return {
            "success": True,
            "path": file_path,
            "line_start": start,
            "line_end": min(
                end,
                len(lines)
            ),
            "content": "\n".join(
                numbered
            )
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


def list_files(
    repository_path: str,
    max_files: int = 1000
):

    repository = Path(
        repository_path
    ).resolve()

    if not repository.exists():

        return {
            "success": False,
            "error": (
                f"Repository not found: "
                f"{repository_path}"
            )
        }

    files = []

    ignored = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        ".next",
        "coverage"
    }

    for root, dirs, filenames in os.walk(
        repository
    ):

        dirs[:] = [
            directory
            for directory in dirs
            if directory not in ignored
        ]

        for filename in filenames:

            full_path = (
                Path(root) / filename
            )

            relative_path = (
                full_path.relative_to(
                    repository
                )
            )

            files.append(
                str(relative_path)
            )

            if len(files) >= max_files:

                return {
                    "success": True,
                    "files": files,
                    "truncated": True
                }

    return {
        "success": True,
        "files": files,
        "truncated": False
    }