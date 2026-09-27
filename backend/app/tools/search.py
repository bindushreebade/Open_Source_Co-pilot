import os
from pathlib import Path


DEFAULT_IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    "coverage",
    ".pytest_cache",
}


def search_code(
    repository_path: str,
    query: str,
    path: str | None = None,
    max_results: int = 50
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
            ),
            "results": []
        }

    if not query:

        return {
            "success": False,
            "error": "Search query cannot be empty.",
            "results": []
        }

    search_root = repository

    if path:

        search_root = (
            repository / path
        ).resolve()

        try:
            search_root.relative_to(
                repository
            )

        except ValueError:

            return {
                "success": False,
                "error": (
                    "Search path escapes repository."
                ),
                "results": []
            }

    if not search_root.exists():

        return {
            "success": False,
            "error": (
                f"Search path not found: {path}"
            ),
            "results": []
        }

    results = []

    query_lower = query.lower()

    for root, dirs, files in os.walk(
        search_root
    ):

        dirs[:] = [
            directory
            for directory in dirs
            if directory not in DEFAULT_IGNORED_DIRECTORIES
        ]

        for filename in files:

            if len(results) >= max_results:
                break

            file_path = (
                Path(root) / filename
            )

            try:

                # Skip obviously binary files
                if file_path.suffix.lower() in {
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".webp",
                    ".ico",
                    ".pdf",
                    ".zip",
                    ".tar",
                    ".gz",
                    ".exe",
                    ".dll",
                    ".so",
                    ".woff",
                    ".woff2",
                    ".ttf",
                    ".mp3",
                    ".mp4",
                }:
                    continue

                content = file_path.read_text(
                    encoding="utf-8",
                    errors="ignore"
                )

            except Exception:

                continue

            for line_number, line in enumerate(
                content.splitlines(),
                start=1
            ):

                if query_lower in line.lower():

                    relative_path = (
                        file_path.relative_to(
                            repository
                        )
                    )

                    results.append({
                        "file": str(
                            relative_path
                        ),
                        "line": line_number,
                        "text": line.strip()
                    })

                    if len(results) >= max_results:
                        break

        if len(results) >= max_results:
            break

    return {
        "success": True,
        "query": query,
        "results": results,
        "count": len(results),
        "truncated": len(results) >= max_results
    }