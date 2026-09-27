import re
import subprocess


CONTAINER_NAME = "coding-agent-sandbox"
WORKSPACE = "/workspace"


# ==========================================================
# TEST SUMMARY
# ==========================================================

def parse_test_summary(stdout: str):
    summary = {}

    match = re.search(
        r"(\d+)\s+passed",
        stdout,
        re.IGNORECASE,
    )

    if match:
        summary["passed"] = int(match.group(1))

    match = re.search(
        r"(\d+)\s+skipped",
        stdout,
        re.IGNORECASE,
    )

    if match:
        summary["skipped"] = int(match.group(1))

    match = re.search(
        r"(\d+)\s+failed",
        stdout,
        re.IGNORECASE,
    )

    if match:
        summary["failed"] = int(match.group(1))

    match = re.search(
        r"(\d+)\s+did not run",
        stdout,
        re.IGNORECASE,
    )

    if match:
        summary["did_not_run"] = int(match.group(1))

    return summary


# ==========================================================
# FAILURE EXTRACTION
# ==========================================================

def extract_test_failures(stdout: str):
    """
    Extract useful Playwright failure information from the
    final test output.

    We intentionally do NOT send the entire test log to Gemini.
    Only the relevant failure sections are returned.
    """

    lines = stdout.splitlines()

    failures = []

    current_failure = []
    inside_failure = False

    # Typical Playwright failure heading:
    #
    # 1) [unit-engine] › test/playwright/unit/foo.spec.mjs:123:5 › ...
    #
    failure_header_pattern = re.compile(
        r"^\s*\d+\)\s+\[.*?\].*"
    )

    # Playwright sometimes prints failure headings in slightly
    # different formats.
    alternate_header_pattern = re.compile(
        r"^\s*\d+\)\s+.*(?:\.spec\.mjs|\.spec\.js|\.test\.js|\.test\.mjs).*"
    )

    for line in lines:

        # --------------------------------------------------
        # New failure block
        # --------------------------------------------------

        if (
            failure_header_pattern.match(line)
            or alternate_header_pattern.match(line)
        ):

            if current_failure:
                failures.append(
                    "\n".join(current_failure).strip()
                )

            current_failure = [line]
            inside_failure = True

            continue

        # --------------------------------------------------
        # Continue current failure
        # --------------------------------------------------

        if inside_failure:

            # Stop when Playwright reaches another major
            # summary section.
            if re.match(
                r"^\s*\d+\s+passed",
                line,
                re.IGNORECASE,
            ):
                if current_failure:
                    failures.append(
                        "\n".join(
                            current_failure
                        ).strip()
                    )

                current_failure = []
                inside_failure = False

                continue

            if re.match(
                r"^\s*\d+\s+failed",
                line,
                re.IGNORECASE,
            ):
                if current_failure:
                    failures.append(
                        "\n".join(
                            current_failure
                        ).strip()
                    )

                current_failure = []
                inside_failure = False

                continue

            current_failure.append(line)

    # ------------------------------------------------------
    # Add final failure
    # ------------------------------------------------------

    if current_failure:
        failures.append(
            "\n".join(
                current_failure
            ).strip()
        )

    # ------------------------------------------------------
    # Fallback
    #
    # If Playwright's output format didn't match the
    # headings above, collect useful error lines instead.
    # ------------------------------------------------------

    if not failures:

        error_lines = []

        for line in lines:

            stripped = line.strip()

            if not stripped:
                continue

            if (
                "Error:" in stripped
                or "Expected:" in stripped
                or "Received:" in stripped
                or "AssertionError" in stripped
                or "TimeoutError" in stripped
                or "failed" in stripped.lower()
            ):
                error_lines.append(stripped)

        if error_lines:
            failures = error_lines

    # ------------------------------------------------------
    # Limit the amount of information sent to Gemini.
    # ------------------------------------------------------

    cleaned_failures = []

    for failure in failures:

        failure = failure.strip()

        if not failure:
            continue

        # Don't allow one enormous failure block.
        if len(failure) > 10000:
            failure = failure[:10000] + (
                "\n...[failure output truncated]"
            )

        cleaned_failures.append(failure)

    # Maximum number of failure blocks.
    return cleaned_failures[:20]


# ==========================================================
# TEST RUNNER
# ==========================================================

def run_tests(
    repository_path: str,
    command: list[str],
    timeout: int = 1800,
    on_output=None,
):
    """
    Run repository tests inside the persistent Docker sandbox.

    The repository is mounted at /workspace.
    """

    try:

        # ==================================================
        # CHECK CONTAINER
        # ==================================================

        check = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{.State.Running}}",
                CONTAINER_NAME,
            ],
            capture_output=True,
            text=True,
        )

        if check.returncode != 0:

            return {
                "success": False,
                "status": "container_error",
                "error": (
                    f"Container "
                    f"'{CONTAINER_NAME}' "
                    f"does not exist."
                ),
            }

        # ==================================================
        # START CONTAINER IF NEEDED
        # ==================================================

        if (
            check.stdout.strip().lower()
            != "true"
        ):

            start_result = subprocess.run(
                [
                    "docker",
                    "start",
                    CONTAINER_NAME,
                ],
                capture_output=True,
                text=True,
            )

            if start_result.returncode != 0:

                return {
                    "success": False,
                    "status": "container_error",
                    "error": (
                        "Failed to start Docker "
                        f"container: "
                        f"{start_result.stderr}"
                    ),
                }

        # ==================================================
        # DOCKER COMMAND
        # ==================================================

        docker_command = [
            "docker",
            "exec",
            "-w",
            WORKSPACE,
            CONTAINER_NAME,
            *command,
        ]

        print(
            "RUNNING:",
            " ".join(docker_command),
        )

        # ==================================================
        # START PROCESS
        # ==================================================

        process = subprocess.Popen(
            docker_command,

            stdout=subprocess.PIPE,

            stderr=subprocess.STDOUT,

            text=True,

            encoding="utf-8",

            errors="replace",

            bufsize=1,
        )

        output_lines = []

        # ==================================================
        # OUTPUT HANDLER
        # ==================================================

        def emit_output(line):

            line = line.rstrip("\n")

            if not line:
                return

            output_lines.append(line)

            print(
                "PLAYWRIGHT RAW:",
                repr(line),
            )

            # ------------------------------------------------
            # Playwright progress:
            #
            # [1579/4423] [unit-engine] › ...
            # ------------------------------------------------

            match = re.search(
                r"\[(\d+)/(\d+)\]",
                line,
            )

            if match:

                completed = int(
                    match.group(1)
                )

                total = int(
                    match.group(2)
                )

                percent = round(
                    (completed / total) * 100,
                    1,
                )

                if on_output:

                    on_output({
                        "type": "test_progress",

                        "completed":
                            completed,

                        "total":
                            total,

                        "percent":
                            percent,

                        "message":
                            line,
                    })

                return

            # ------------------------------------------------
            # Normal output
            # ------------------------------------------------

            if on_output:

                on_output({
                    "type": "test_output",

                    "message": line,
                })

        # ==================================================
        # READ OUTPUT
        # ==================================================

        try:

            while True:

                line = (
                    process.stdout.readline()
                )

                if (
                    line == ""
                    and process.poll()
                    is not None
                ):
                    break

                if line:
                    emit_output(line)

            process.wait(
                timeout=timeout
            )

        except subprocess.TimeoutExpired:

            process.kill()

            process.wait()

            stdout = "\n".join(
                output_lines
            )

            return {
                "success": False,
                "status": "timeout",
                "exit_code": -1,
                "stdout": stdout,
                "stderr": "",
                "summary":
                    parse_test_summary(
                        stdout
                    ),
                "failures":
                    extract_test_failures(
                        stdout
                    ),
                "command": command,
            }

        # ==================================================
        # COLLECT RESULT
        # ==================================================

        stdout = "\n".join(
            output_lines
        )

        exit_code = (
            process.returncode
        )

        summary = (
            parse_test_summary(
                stdout
            )
        )

        failures = (
            extract_test_failures(
                stdout
            )
        )

        # ==================================================
        # DETERMINE STATUS
        # ==================================================

        if exit_code == 0:

            status = "passed"
            success = True

        else:

            status = "failed"
            success = False

        # ==================================================
        # RESULT
        # ==================================================

        result = {
            "success": success,

            "status": status,

            "exit_code": exit_code,

            "stdout": stdout,

            "stderr": "",

            "summary": summary,

            "failures": failures,

            "command": command,
        }

        # ==================================================
        # STREAM TEST RESULT
        # ==================================================

        if on_output:

            on_output({
                "type": "test_result",

                "success":
                    success,

                "status":
                    status,

                "exit_code":
                    exit_code,

                "summary":
                    summary,

                "failures":
                    failures,
            })

        return result

    # ======================================================
    # RUNNER ERROR
    # ======================================================

    except Exception as e:

        return {
            "success": False,

            "status":
                "runner_error",

            "error":
                str(e),

            "command":
                command,
        }