from pathlib import Path


def apply_patch(
    repository_path: str,
    file_path: str,
    old_text: str,
    new_text: str
):
    """
    Safely replace an exact piece of text inside a repository file.

    The patch is applied only when:
    - the repository exists
    - the target file exists
    - the target is inside the repository
    - old_text exists exactly once

    This prevents the AI agent from accidentally modifying
    the wrong part of a file.
    """

    try:

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

        target = (
            repository / file_path
        ).resolve()

        # ------------------------------------------
        # Security: prevent path traversal
        # ------------------------------------------

        try:

            target.relative_to(
                repository
            )

        except ValueError:

            return {
                "success": False,
                "error": (
                    "Patch file is outside "
                    "the repository."
                )
            }

        # ------------------------------------------
        # Check file
        # ------------------------------------------

        if not target.exists():

            return {
                "success": False,
                "error": (
                    f"File not found: "
                    f"{file_path}"
                )
            }

        if not target.is_file():

            return {
                "success": False,
                "error": (
                    f"Target is not a file: "
                    f"{file_path}"
                )
            }

        # ------------------------------------------
        # Validate patch input
        # ------------------------------------------

        if not old_text:

            return {
                "success": False,
                "error": (
                    "old_text cannot be empty."
                )
            }

        if old_text == new_text:

            return {
                "success": False,
                "error": (
                    "old_text and new_text "
                    "are identical."
                )
            }

        # ------------------------------------------
        # Read file
        # ------------------------------------------

        content = target.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        # ------------------------------------------
        # Make sure exact text exists
        # ------------------------------------------

        occurrences = content.count(
            old_text
        )

        if occurrences == 0:

            return {
                "success": False,
                "error": (
                    "The exact old_text was "
                    "not found in the file."
                ),
                "file": file_path
            }

        # ------------------------------------------
        # Prevent ambiguous patches
        # ------------------------------------------

        if occurrences > 1:

            return {
                "success": False,
                "error": (
                    f"old_text occurs "
                    f"{occurrences} times. "
                    "Patch was not applied because "
                    "the target is ambiguous."
                ),
                "file": file_path,
                "occurrences": occurrences
            }

        # ------------------------------------------
        # Apply replacement
        # ------------------------------------------

        updated_content = content.replace(
            old_text,
            new_text,
            1
        )

        # ------------------------------------------
        # Safety check
        # ------------------------------------------

        if updated_content == content:

            return {
                "success": False,
                "error": (
                    "Patch produced no changes."
                ),
                "file": file_path
            }

        # ------------------------------------------
        # Write file
        # ------------------------------------------

        target.write_text(
            updated_content,
            encoding="utf-8"
        )

        # ------------------------------------------
        # Verify patch
        # ------------------------------------------

        verify_content = target.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        if old_text in verify_content:

            return {
                "success": False,
                "error": (
                    "Patch verification failed: "
                    "old_text still exists."
                ),
                "file": file_path
            }

        if new_text not in verify_content:

            return {
                "success": False,
                "error": (
                    "Patch verification failed: "
                    "new_text was not found."
                ),
                "file": file_path
            }

        # ------------------------------------------
        # Success
        # ------------------------------------------

        return {
            "success": True,
            "file": file_path,
            "message": (
                "Patch applied successfully."
            ),
            "occurrences_replaced": 1
        }

    except UnicodeDecodeError:

        return {
            "success": False,
            "error": (
                "File is not a supported UTF-8 "
                "text file."
            )
        }

    except PermissionError:

        return {
            "success": False,
            "error": (
                "Permission denied while "
                "modifying the file."
            )
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }