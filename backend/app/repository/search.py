import os
import subprocess


class CodeSearcher:

    def search(
        self,
        repository_path: str,
        query: str,
        max_results: int = 20
    ):
        repository_path = os.path.abspath(repository_path)

        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    repository_path,
                    "grep",
                    "-n",
                    "-i",
                    "--",
                    query
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore"
            )

        except Exception as e:
            return {
                "error": str(e)
            }

        if result.returncode not in (0, 1):
            return {
                "error": result.stderr.strip()
            }

        results = []

        for line in result.stdout.splitlines():

            parts = line.split(":", 2)

            if len(parts) != 3:
                continue

            file_path, line_number, match = parts

            results.append({
                "file": file_path,
                "line": int(line_number),
                "match": match.strip()
            })

            if len(results) >= max_results:
                break

        return results