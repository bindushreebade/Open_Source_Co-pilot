import re
import subprocess


CONTAINER_NAME = "coding-agent-sandbox"
WORKSPACE = "/workspace"


def parse_test_summary(stdout: str):
    summary = {}

    # Example:
    # 4414 passed (12.5m)
    match = re.search(r"(\d+)\s+passed", stdout, re.IGNORECASE)
    if match:
        summary["passed"] = int(match.group(1))

    match = re.search(r"(\d+)\s+skipped", stdout, re.IGNORECASE)
    if match:
        summary["skipped"] = int(match.group(1))

    match = re.search(r"(\d+)\s+failed", stdout, re.IGNORECASE)
    if match:
        summary["failed"] = int(match.group(1))

    match = re.search(r"(\d+)\s+did not run", stdout, re.IGNORECASE)
    if match:
        summary["did_not_run"] = int(match.group(1))

    return summary


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
        # Make sure the container is running
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
                "error": f"Container '{CONTAINER_NAME}' does not exist.",
            }

        if check.stdout.strip().lower() != "true":
            subprocess.run(
                ["docker", "start", CONTAINER_NAME],
                check=True,
                capture_output=True,
                text=True,
            )

        # Send command into the existing container
        docker_command = [
            "docker",
            "exec",
            "-w",
            WORKSPACE,
            CONTAINER_NAME,
            *command,
        ]

        print("RUNNING:", " ".join(docker_command))

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

        def emit_output(line):
            line = line.rstrip("\n")

            if not line:
                return

            output_lines.append(line)

            print("PLAYWRIGHT RAW:", repr(line))

            # Playwright format:
            # [1579/4423] [unit-engine] › ...
            match = re.search(r"\[(\d+)/(\d+)\]", line)

            if match:
                completed = int(match.group(1))
                total = int(match.group(2))

                percent = round((completed / total) * 100, 1)

                if on_output:
                    on_output({
                        "type": "test_progress",
                        "completed": completed,
                        "total": total,
                        "percent": percent,
                        "message": line,
                    })

                return

            if on_output:
                on_output({
                    "type": "test_output",
                    "message": line,
                })

        try:
            while True:
                line = process.stdout.readline()

                if line == "" and process.poll() is not None:
                    break

                if line:
                    emit_output(line)

            process.wait(timeout=timeout)

        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

            return {
                "success": False,
                "status": "timeout",
                "exit_code": -1,
                "stdout": "\n".join(output_lines),
                "stderr": "",
            }

        stdout = "\n".join(output_lines)
        exit_code = process.returncode

        summary = parse_test_summary(stdout)

        if exit_code == 0:
            status = "passed"
            success = True
        else:
            status = "failed"
            success = False

        result = {
            "success": success,
            "status": status,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": "",
            "summary": summary,
            "command": command,
        }

        if on_output:
            on_output({
                "type": "test_result",
                "success": success,
                "status": status,
                "exit_code": exit_code,
                "summary": summary,
            })

        return result

    except Exception as e:
        return {
            "success": False,
            "status": "runner_error",
            "error": str(e),
            "command": command,
        }