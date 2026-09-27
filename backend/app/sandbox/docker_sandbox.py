import subprocess
import os


class DockerSandbox:

    def __init__(self, repository_path: str):
        self.repository_path = os.path.abspath(repository_path)
        self.container_name = "coding-agent-sandbox"

    def start(self):
        """Make sure the general sandbox container is running."""

        result = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{.State.Running}}",
                self.container_name,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Docker container '{self.container_name}' does not exist."
            )

        if result.stdout.strip().lower() != "true":
            subprocess.run(
                ["docker", "start", self.container_name],
                check=True,
                capture_output=True,
                text=True,
            )

    def run(self, command: list[str], timeout: int = 600, on_output=None):
        """Run a command inside the sandbox container."""

        docker_command = [
            "docker",
            "exec",
            "-i",
            "-w",
            "/workspace",
            self.container_name,
            *command,
        ]

        # Make repository available inside the container.
        # The repository must already be mounted at /workspace.
        process = subprocess.Popen(
            docker_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        stdout_lines = []
        stderr_lines = []

        try:
            stdout, stderr = process.communicate(timeout=timeout)

        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()

            return {
                "success": False,
                "exit_code": -1,
                "stdout": stdout,
                "stderr": stderr,
                "status": "timeout",
            }

        if stdout:
            for line in stdout.splitlines():
                stdout_lines.append(line)

                if on_output:
                    on_output(line)

        if stderr:
            stderr_lines.extend(stderr.splitlines())

        return {
            "success": process.returncode == 0,
            "exit_code": process.returncode,
            "stdout": "\n".join(stdout_lines),
            "stderr": "\n".join(stderr_lines),
            "status": "passed" if process.returncode == 0 else "failed",
        }

    def stop(self):
        """Stop the sandbox container."""

        subprocess.run(
            ["docker", "stop", self.container_name],
            capture_output=True,
            text=True,
        )