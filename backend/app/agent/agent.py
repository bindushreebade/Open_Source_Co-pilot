import json
import os
from typing import Optional, Callable

from google import genai

from app.tools.github import get_issue
from app.tools.repository import read_file
from app.tools.search import search_code
from app.tools.patch import apply_patch
from app.tools.test_runner import run_tests


class CodingAgent:

    def __init__(self):
        self.client = genai.Client()
        self.model = "gemini-3.5-flash-lite"

        # Investigation limits
        self.max_investigation_rounds = 3
        self.max_searches_per_round = 6
        self.max_files_per_round = 5

        # Repair limit
        self.max_repair_attempts = 2

    # ==========================================================
    # Helpers
    # ==========================================================

    def _parse_json(self, text: str):

        text = (text or "").strip()

        try:
            return json.loads(text)
        except Exception:
            pass

        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1:
            raise ValueError(
                "Gemini did not return valid JSON."
            )

        return json.loads(text[start:end + 1])

    # ----------------------------------------------------------

    def _file_exists(
        self,
        repository_path: str,
        file_path: str,
    ) -> bool:

        if not file_path:
            return False

        file_path = file_path.strip()

        full_path = os.path.abspath(
            os.path.join(
                repository_path,
                file_path,
            )
        )

        repository_root = os.path.abspath(
            repository_path
        )

        if not (
            full_path == repository_root
            or full_path.startswith(
                repository_root + os.sep
            )
        ):
            return False

        return os.path.isfile(full_path)

    # ----------------------------------------------------------

    def _read_exact_file(
        self,
        repository_path: str,
        file_path: str,
    ) -> Optional[str]:

        if not self._file_exists(
            repository_path,
            file_path,
        ):
            return None

        full_path = os.path.abspath(
            os.path.join(
                repository_path,
                file_path,
            )
        )

        try:
            with open(
                full_path,
                "r",
                encoding="utf-8",
                errors="replace",
            ) as f:
                return f.read()

        except Exception:
            return None

    # ----------------------------------------------------------

    def _patch_is_valid(
        self,
        repository_path: str,
        patch_file: str,
        old_text: str,
    ):

        if not self._file_exists(
            repository_path,
            patch_file,
        ):
            return (
                False,
                f"Target is not a file: {patch_file}",
            )

        content = self._read_exact_file(
            repository_path,
            patch_file,
        )

        if content is None:
            return (
                False,
                f"Could not read target file: {patch_file}",
            )

        if not old_text:
            return (
                False,
                "Patch old_text is empty.",
            )

        if old_text not in content:
            return (
                False,
                "The proposed old_text does not exist "
                f"exactly in {patch_file}.",
            )

        return True, None

    # ==========================================================
    # Investigation
    # ==========================================================

    def _execute_investigation_round(
        self,
        repository_path: str,
        investigation: dict,
        evidence: list,
        log,
    ):

        useful_evidence = 0

        searches = investigation.get(
            "searches",
            [],
        )

        files = investigation.get(
            "files",
            [],
        )

        log(
            "→ Executing repository searches..."
        )

        for search in searches[
            :self.max_searches_per_round
        ]:

            query = str(
                search.get(
                    "query",
                    "",
                )
            ).strip()

            path = search.get("path")

            if not query:
                continue

            if path:
                log(
                    f"  → Searching `{query}` "
                    f"in `{path}`"
                )
            else:
                log(
                    f"  → Searching `{query}`"
                )

            try:

                result = search_code(
                    repository_path,
                    query,
                    path,
                )

            except Exception as e:

                result = {
                    "success": False,
                    "error": str(e),
                }

            evidence.append({
                "type": "search",
                "query": query,
                "path": path,
                "result": result,
            })

            if isinstance(result, dict):

                if result.get(
                    "success"
                ) is False:
                    continue

                results = result.get(
                    "results"
                )

                if results:
                    useful_evidence += 1

                elif result.get("matches"):
                    useful_evidence += 1

                elif result.get("files"):
                    useful_evidence += 1

                elif result.get("content"):
                    useful_evidence += 1

            elif result:

                useful_evidence += 1

        # ------------------------------------------------------

        log(
            "→ Inspecting candidate source files..."
        )

        for file_info in files[:self.max_files_per_round]:

            if isinstance(file_info, str):
                file_path = file_info.strip()
                line_start = None
                line_end = None
                reason = ""

            elif isinstance(file_info, dict):
                file_path = str(
                    file_info.get("path", "")
                ).strip()

                line_start = file_info.get(
                    "line_start"
                )

                line_end = file_info.get(
                    "line_end"
                )

                reason = str(
                    file_info.get("reason", "")
                )

            else:
                continue

            if not file_path:
                continue

            if not self._file_exists(
                repository_path,
                file_path,
            ):
                log(
                    "  ⚠️ Candidate does not exist: "
                    f"{file_path}"
                )
                continue

            log(
                f"  → Reading `{file_path}`"
            )

            try:
                result = read_file(
                    repository_path,
                    file_path,
                    line_start,
                    line_end,
                )

            except Exception as e:
                result = {
                    "success": False,
                    "error": str(e),
                }

            evidence.append({
                "type": "file",
                "path": file_path,
                "reason": reason,
                "result": result,
            })

            if isinstance(result, dict):
                if result.get("success") is not False:
                    useful_evidence += 1

            elif result:
                useful_evidence += 1

        return useful_evidence

    # ==========================================================
    # Repair
    # ==========================================================

    def _generate_repair(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        issue_title: str,
        issue_body: str,
        analysis: dict,
        test_result: dict,
        repository_path: str,
        log,
    ):

        summary = test_result.get(
            "summary",
            {},
        )

        failures = test_result.get(
            "failures",
            [],
        )

        failure_text = json.dumps(
            failures,
            indent=2,
            default=str,
        )

        if len(failure_text) > 60000:
            failure_text = failure_text[-60000:]

        repair_prompt = f"""
You are repairing a patch in a real open-source repository.

Repository:
{owner}/{repo}

Issue:
#{issue_number}

Issue title:
{issue_title}

Issue description:
{issue_body}

Original root cause:
{analysis.get("root_cause", "")}

Original explanation:
{analysis.get("explanation", "")}

Original patch:
{json.dumps(
    analysis.get("patch"),
    indent=2,
    default=str,
)}

Test summary:
{json.dumps(
    summary,
    indent=2,
    default=str,
)}

Test failures:
{failure_text}

The patch has already been applied.

Your job is to determine whether the failures
were caused by our patch.

IMPORTANT:

1. Do not modify unrelated code.
2. Do not invent filenames.
3. Do not invent functions.
4. Use actual repository evidence.
5. If failures are unrelated to our patch,
   return patch = null.
6. If the patch caused the failures,
   return the smallest corrective patch.
7. The target file must exist.
8. old_text must exactly exist in the current file.

Return ONLY JSON.

If no repair is justified:

{{
    "reason": "explanation",
    "patch": null
}}

If a repair is required:

{{
    "reason": "explanation",
    "patch": {{
        "file": "repository-relative path",
        "old_text": "exact existing text",
        "new_text": "replacement text"
    }}
}}
"""

        log(
            "→ Gemini is analyzing the failed tests..."
        )

        try:

            response = (
                self.client.models.generate_content(
                    model=self.model,
                    contents=repair_prompt,
                )
            )

        except Exception as e:

            log(
                f"❌ Gemini repair request failed: {e}"
            )

            return None

        try:

            return self._parse_json(
                response.text or ""
            )

        except Exception as e:

            log(
                "❌ Gemini returned invalid repair JSON: "
                f"{e}"
            )

            return None

    # ==========================================================
    # Main Agent
    # ==========================================================

    def run(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        repository_path: str,
        emit: Optional[Callable] = None,
    ):

        def log(*messages):

            message = " ".join(
                str(m)
                for m in messages
            )

            print(message)

            if emit:

                emit({
                    "type": "log",
                    "message": message,
                })

        # ======================================================
        # 1. Fetch Issue
        # ======================================================

        log(
            f"→ Fetching GitHub issue #{issue_number}..."
        )

        issue = get_issue(
            owner,
            repo,
            issue_number,
        )

        if not issue.get("success"):

            log(
                "❌ Failed to fetch GitHub issue."
            )

            return {
                "status": "issue_fetch_failed",
                "error": issue.get("error"),
            }

        log("✓ Issue fetched.")

        issue_title = issue.get(
            "title",
            "",
        )

        issue_body = issue.get(
            "body",
            "",
        )

        log(
            f"→ Issue: {issue_title}"
        )

        # ======================================================
        # 2. Investigation Plan
        # ======================================================

        log(
            "→ Asking Gemini for an investigation plan..."
        )

        investigation_prompt = f"""
You are an expert software engineer investigating
a GitHub issue in a real open-source repository.

Repository:
{owner}/{repo}

Issue:
#{issue_number}

Title:
{issue_title}

Description:
{issue_body}

Create an investigation plan.

Do NOT solve the issue yet.

Important:

- Do not assume filenames mentioned in the issue exist.
- Search for function names.
- Search for class names.
- Search distinctive strings.
- Search callers and imports.
- Search related directories.
- Do not invent paths.

Return ONLY JSON:

{{
    "searches": [
        {{
            "query": "string",
            "path": "optional directory"
        }}
    ],
    "files": [
        {{
            "path": "repository-relative path",
            "line_start": 1,
            "line_end": 150
        }}
    ]
}}
"""

        try:

            response = (
                self.client.models.generate_content(
                    model=self.model,
                    contents=investigation_prompt,
                )
            )

            investigation = self._parse_json(
                response.text or ""
            )

        except Exception as e:

            log(
                f"❌ Invalid investigation plan: {e}"
            )

            return {
                "status": "investigation_failed",
                "error": str(e),
            }

        log(
            "✓ Initial investigation plan ready."
        )

        # ======================================================
        # 3. Adaptive Investigation
        # ======================================================

        evidence = []

        for round_number in range(
            1,
            self.max_investigation_rounds + 1,
        ):

            log("")

            log(
                f"🔎 Investigation round "
                f"{round_number}/"
                f"{self.max_investigation_rounds}"
            )

            useful_evidence = (
                self._execute_investigation_round(
                    repository_path,
                    investigation,
                    evidence,
                    log,
                )
            )

            log(
                f"  → Useful evidence found: "
                f"{useful_evidence}"
            )

            if round_number >= (
                self.max_investigation_rounds
            ):
                break

            recent_evidence = evidence[-30:]

            evidence_text = json.dumps(
                recent_evidence,
                indent=2,
                default=str,
            )

            refinement_prompt = f"""
You are continuing investigation of a
GitHub issue.

Repository:
{owner}/{repo}

Issue:
#{issue_number}

Title:
{issue_title}

Description:
{issue_body}

Evidence:
{evidence_text}

Determine whether the actual implementation
has been located.

If not, create broader searches.

Do not repeat searches that failed.

Consider:

- alternate function names
- classes
- callers
- imports
- strings
- directories
- utilities
- neighboring functionality

Return ONLY JSON:

{{
    "found": true or false,
    "reason": "short explanation",
    "searches": [],
    "files": []
}}
"""

            try:

                refinement_response = (
                    self.client.models.generate_content(
                        model=self.model,
                        contents=refinement_prompt,
                    )
                )

                next_investigation = (
                    self._parse_json(
                        refinement_response.text
                        or ""
                    )
                )

            except Exception as e:

                log(
                    f"⚠️ Investigation refinement failed: {e}"
                )

                break

            if next_investigation.get(
                "found"
            ) is True:

                log(
                    "✓ Gemini believes the relevant "
                    "implementation has been located."
                )

                investigation = (
                    next_investigation
                )

                self._execute_investigation_round(
                    repository_path,
                    investigation,
                    evidence,
                    log,
                )

                break

            next_searches = (
                next_investigation.get(
                    "searches",
                    [],
                )
            )

            next_files = (
                next_investigation.get(
                    "files",
                    [],
                )
            )

            if not next_searches and not next_files:

                log(
                    "⚠️ No further investigation path."
                )

                break

            log(
                "→ Gemini requested broader investigation."
            )

            investigation = (
                next_investigation
            )

        # ======================================================
        # 4. Evidence Check
        # ======================================================

        if not evidence:

            log(
                "❌ No repository evidence collected."
            )

            return {
                "status": "insufficient_evidence",
                "error": (
                    "No useful repository evidence."
                ),
            }

        # ======================================================
        # 5. Root Cause Analysis
        # ======================================================

        log(
            "→ Analyzing repository evidence..."
        )

        evidence_text = json.dumps(
            evidence,
            indent=2,
            default=str,
        )

        if len(evidence_text) > 120000:
            evidence_text = evidence_text[-120000:]

        analysis_prompt = f"""
You are an expert software engineer working
on a real open-source repository.

Repository:
{owner}/{repo}

Issue:
#{issue_number}

Title:
{issue_title}

Description:
{issue_body}

Repository evidence:

{evidence_text}

Determine the actual root cause.

IMPORTANT:

1. Use repository evidence.
2. Do not invent filenames.
3. Do not invent functions.
4. Do not invent code.
5. The patch file must exist.
6. old_text must be exact.
7. Keep the patch minimal.
8. If evidence is insufficient, patch = null.

Return ONLY JSON:

{{
    "root_cause": "string",
    "explanation": "string",
    "patch": null
}}

OR:

{{
    "root_cause": "string",
    "explanation": "string",
    "patch": {{
        "file": "repository-relative path",
        "old_text": "exact existing text",
        "new_text": "replacement text"
    }}
}}
"""

        try:

            response = (
                self.client.models.generate_content(
                    model=self.model,
                    contents=analysis_prompt,
                )
            )

            analysis = self._parse_json(
                response.text or ""
            )

        except Exception as e:

            log(
                f"❌ Gemini analysis failed: {e}"
            )

            return {
                "status": "analysis_failed",
                "error": str(e),
            }

        log(
            "✓ Gemini analysis complete."
        )

        if emit:

            emit({
                "type": "analysis",
                "root_cause": analysis.get(
                    "root_cause"
                ),
                "explanation": analysis.get(
                    "explanation"
                ),
            })

        # ======================================================
        # 6. Initial Patch
        # ======================================================

        patch = analysis.get("patch")

        if not patch:

            log(
                "⚠️ No evidence-backed patch produced."
            )

            analysis["status"] = (
                "insufficient_evidence"
            )

            analysis["repair_attempts"] = 0

            if emit:

                emit({
                    "type": "final",
                    "status": analysis["status"],
                    "repair_attempts": 0,
                })

            return analysis

        patch_file = str(
            patch.get(
                "file",
                "",
            )
        ).strip()

        old_text = patch.get(
            "old_text",
            "",
        )

        new_text = patch.get(
            "new_text",
            "",
        )

        log(
            f"→ Patch target: {patch_file}"
        )

        valid_patch, validation_error = (
            self._patch_is_valid(
                repository_path,
                patch_file,
                old_text,
            )
        )

        if not valid_patch:

            log(
                f"❌ Patch rejected: "
                f"{validation_error}"
            )

            if emit:

                emit({
                    "type": "error",
                    "message": validation_error,
                })

            analysis["status"] = (
                "patch_validation_failed"
            )

            analysis["repair_attempts"] = 0

            if emit:

                emit({
                    "type": "final",
                    "status": analysis["status"],
                    "repair_attempts": 0,
                })

            return analysis

        log(
            "✓ Patch target exists and old_text matches."
        )

        # ======================================================
        # 7. Apply Initial Patch
        # ======================================================

        log(
            f"→ Applying patch to: {patch_file}"
        )

        patch_result = apply_patch(
            repository_path=repository_path,
            file_path=patch_file,
            old_text=old_text,
            new_text=new_text,
        )

        if not patch_result.get("success"):

            log(
                "❌ Patch application failed."
            )

            analysis["status"] = "patch_failed"
            analysis["repair_attempts"] = 0

            return analysis

        log(
            "✅ Patch applied successfully."
        )

        if emit:

            emit({
                "type": "patch",
                "file": patch_file,
                "old_text": old_text,
                "new_text": new_text,
                "success": True,
                "repair_attempt": 0,
            })

        # ======================================================
        # 8. Test + Repair Loop
        # ======================================================

        repair_attempts = 0

        while True:

            log("")

            if repair_attempts == 0:

                log(
                    "→ Running tests inside Docker sandbox..."
                )

            else:

                log(
                    f"→ Re-running tests after "
                    f"repair attempt "
                    f"{repair_attempts}..."
                )

            if emit:

                emit({
                    "type": "test_started",
                    "repair_attempt": repair_attempts,
                    "message": (
                        "Running test suite..."
                        if repair_attempts == 0
                        else (
                            f"Running tests after "
                            f"repair {repair_attempts}/"
                            f"{self.max_repair_attempts}..."
                        )
                    ),
                })

            def test_output(event):

                if emit:

                    event = dict(event)

                    event[
                        "repair_attempt"
                    ] = repair_attempts

                    emit(event)

            test_result = run_tests(
                repository_path,
                [
                    "npm",
                    "run",
                    "test-unit",
                    "--",
                    "--reporter=line",
                ],
                timeout=1800,
                on_output=test_output,
            )

            analysis["test_result"] = (
                test_result
            )

            test_status = test_result.get(
                "status"
            )

            summary = test_result.get(
                "summary"
            )

            log(
                f"→ Test status: {test_status}"
            )

            if isinstance(summary, dict):

                log(
                    f"  • Passed: "
                    f"{summary.get('passed', 0)}"
                )

                log(
                    f"  • Failed: "
                    f"{summary.get('failed', 0)}"
                )

                log(
                    f"  • Skipped: "
                    f"{summary.get('skipped', 0)}"
                )

                log(
                    f"  • Did not run: "
                    f"{summary.get('did_not_run', 0)}"
                )

            # --------------------------------------------------
            # Send test result
            # --------------------------------------------------

            if emit:

                emit({
                    "type": "test_result",
                    "status": test_status,
                    "success": test_result.get(
                        "success"
                    ),
                    "exit_code": test_result.get(
                        "exit_code"
                    ),
                    "summary": summary,
                    "repair_attempt": repair_attempts,
                })

            # ==================================================
            # SUCCESS
            # ==================================================

            if test_status == "passed":

                log(
                    "🎉 All tests passed."
                )

                analysis["status"] = (
                    "verified"
                )

                analysis["repair_attempts"] = (
                    repair_attempts
                )

                break

            # ==================================================
            # NON-REPAIRABLE
            # ==================================================

            if test_status in (
                "timeout",
                "dependency_install_failed",
            ):

                if test_status == "timeout":

                    log(
                        "⏱️ Tests timed out."
                    )

                else:

                    log(
                        "❌ Dependency installation failed."
                    )

                analysis["status"] = (
                    test_status
                )

                analysis["repair_attempts"] = (
                    repair_attempts
                )

                break

            # ==================================================
            # UNKNOWN TEST ERROR
            # ==================================================

            if test_status != "failed":

                log(
                    "⚠️ Test runner did not "
                    "complete successfully."
                )

                analysis["status"] = (
                    test_status
                    or "test_error"
                )

                analysis["repair_attempts"] = (
                    repair_attempts
                )

                break

            # ==================================================
            # FAILURE
            # ==================================================

            log(
                "❌ Tests failed."
            )

            # --------------------------------------------------
            # Maximum attempts
            # --------------------------------------------------

            if (
                repair_attempts
                >= self.max_repair_attempts
            ):

                log(
                    "🛑 Maximum repair attempts reached."
                )

                analysis["status"] = (
                    "tests_failed"
                )

                analysis["repair_attempts"] = (
                    repair_attempts
                )

                break

            # --------------------------------------------------
            # Start repair
            # --------------------------------------------------

            repair_attempts += 1

            log("")

            log(
                f"🔧 Repair attempt "
                f"{repair_attempts}/"
                f"{self.max_repair_attempts}"
            )

            if emit:

                emit({
                    "type": "repair_started",
                    "repair_attempt": repair_attempts,
                    "repair_attempts": (
                        self.max_repair_attempts
                    ),
                    "message": (
                        f"Analyzing failures "
                        f"for repair "
                        f"{repair_attempts}/"
                        f"{self.max_repair_attempts}"
                    ),
                })

            repair = self._generate_repair(
                owner=owner,
                repo=repo,
                issue_number=issue_number,
                issue_title=issue_title,
                issue_body=issue_body,
                analysis=analysis,
                test_result=test_result,
                repository_path=repository_path,
                log=log,
            )

            if not repair:

                analysis["status"] = (
                    "tests_failed"
                )

                analysis["repair_attempts"] = (
                    repair_attempts
                )

                break

            repair_reason = repair.get(
                "reason",
                "No explanation provided.",
            )

            log(
                f"→ Repair analysis: "
                f"{repair_reason}"
            )

            repair_patch = repair.get(
                "patch"
            )

            # Gemini says no repair is justified.

            if not repair_patch:

                log(
                    "⚠️ No safe repair identified."
                )

                analysis["status"] = (
                    "tests_failed"
                )

                analysis["repair_attempts"] = (
                    repair_attempts
                )

                break

            repair_file = str(
                repair_patch.get(
                    "file",
                    "",
                )
            ).strip()

            repair_old_text = (
                repair_patch.get(
                    "old_text",
                    "",
                )
            )

            repair_new_text = (
                repair_patch.get(
                    "new_text",
                    "",
                )
            )

            log(
                f"→ Repair target: "
                f"{repair_file}"
            )

            # --------------------------------------------------
            # Validate repair
            # --------------------------------------------------

            valid_repair, repair_error = (
                self._patch_is_valid(
                    repository_path,
                    repair_file,
                    repair_old_text,
                )
            )

            if not valid_repair:

                log(
                    f"❌ Repair patch rejected: "
                    f"{repair_error}"
                )

                if emit:

                    emit({
                        "type": "error",
                        "message": repair_error,
                        "repair_attempt": (
                            repair_attempts
                        ),
                    })

                analysis["status"] = (
                    "tests_failed"
                )

                analysis["repair_attempts"] = (
                    repair_attempts
                )

                break

            # --------------------------------------------------
            # Apply repair
            # --------------------------------------------------

            log(
                "✓ Repair patch validated."
            )

            log(
                f"→ Applying repair patch to "
                f"{repair_file}"
            )

            repair_result = apply_patch(
                repository_path=repository_path,
                file_path=repair_file,
                old_text=repair_old_text,
                new_text=repair_new_text,
            )

            if not repair_result.get(
                "success"
            ):

                log(
                    "❌ Repair patch application failed."
                )

                analysis["status"] = (
                    "tests_failed"
                )

                analysis["repair_attempts"] = (
                    repair_attempts
                )

                break

            log(
                "✅ Repair patch applied successfully."
            )

            if emit:

                emit({
                    "type": "patch",
                    "file": repair_file,
                    "old_text": repair_old_text,
                    "new_text": repair_new_text,
                    "success": True,
                    "repair_attempt": (
                        repair_attempts
                    ),
                })

            # Loop back and run tests again.

        # ======================================================
        # Final Event
        # ======================================================

        if emit:

            emit({
                "type": "final",
                "status": analysis.get(
                    "status"
                ),
                "repair_attempts": analysis.get(
                    "repair_attempts",
                    0,
                ),
            })

        return analysis