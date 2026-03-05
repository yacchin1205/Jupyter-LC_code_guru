#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from ipykernel.kernelapp import IPKernelApp
from ipykernel.kernelbase import Kernel


class CodexKernel(Kernel):
    implementation = "codex_kernel"
    implementation_version = "0.1.0"
    language = "codex"
    language_version = "1"
    language_info = {
        "name": "codex",
        "mimetype": "text/plain",
        "file_extension": ".prompt",
    }
    banner = "Codex Kernel (1 kernel = 1 Codex session)"
    _UNAUTHORIZED_MARKER = "unexpected status 401 Unauthorized"
    _LOGIN_COMMAND = "%%login"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._thread_id: str | None = None
        self._show_events = os.environ.get("CODEX_KERNEL_SHOW_EVENTS", "0") == "1"

    def _build_command(self, code: str) -> list[str]:
        if self._thread_id is None:
            return [
                "codex",
                "exec",
                "--json",
                "--skip-git-repo-check",
                code,
            ]
        return [
            "codex",
            "exec",
            "resume",
            "--json",
            "--skip-git-repo-check",
            self._thread_id,
            code,
        ]

    def _collect_stdout_text(self, stdout: str) -> tuple[str, str | None, str]:
        rendered: list[str] = []
        last_error: str | None = None
        stderr_lines: list[str] = []
        for line in stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            event = json.loads(stripped)
            event_type = event["type"]
            if event_type == "thread.started":
                self._thread_id = event["thread_id"]
            elif event_type == "item.completed":
                item = event["item"]
                if item["type"] == "agent_message":
                    rendered.append(item["text"])
            elif event_type == "error":
                stderr_lines.append(event["message"])
            elif event_type == "turn.failed":
                last_error = event["error"]["message"]
            if self._show_events:
                rendered.append(stripped)
        return ("\n".join(rendered), last_error, "\n".join(stderr_lines))

    def _run_device_auth_login(self) -> tuple[int, str]:
        proc = subprocess.Popen(
            ["codex", "login", "--device-auth"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        login_lines: list[str] = []
        if proc.stdout is not None:
            for line in proc.stdout:
                login_lines.append(line.rstrip("\n"))
                self.send_response(
                    self.iopub_socket,
                    "stream",
                    {"name": "stdout", "text": line},
                )
        returncode = proc.wait()
        return (returncode, "\n".join(login_lines))

    def do_execute(
        self,
        code: str,
        silent: bool,
        store_history: bool = True,
        user_expressions: dict[str, Any] | None = None,
        allow_stdin: bool = False,
        *,
        cell_meta: dict[str, Any] | None = None,
        cell_id: str | None = None,
    ) -> dict[str, Any]:
        if not code.strip():
            return {"status": "ok", "execution_count": self.execution_count, "payload": [], "user_expressions": {}}
        if code.strip() == self._LOGIN_COMMAND:
            login_returncode, _ = self._run_device_auth_login()
            if login_returncode != 0:
                return {
                    "status": "error",
                    "ename": "CodexLoginError",
                    "evalue": f"codex login exited with status {login_returncode}",
                    "traceback": [f"Command failed: codex login --device-auth"],
                }
            return {"status": "ok", "execution_count": self.execution_count, "payload": [], "user_expressions": {}}

        cmd = self._build_command(code)
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        stdout_text, last_error, event_stderr = self._collect_stdout_text(proc.stdout)

        if not silent:
            if stdout_text:
                self.send_response(
                    self.iopub_socket,
                    "stream",
                    {"name": "stdout", "text": stdout_text},
                )
            stderr_parts: list[str] = []
            if proc.stderr:
                stderr_parts.append(proc.stderr)
            if event_stderr:
                stderr_parts.append(event_stderr)
            if stderr_parts:
                self.send_response(
                    self.iopub_socket,
                    "stream",
                    {"name": "stderr", "text": "\n".join(stderr_parts)},
                )

        if proc.returncode != 0:
            evalue = f"codex exited with status {proc.returncode}"
            if last_error is not None:
                evalue = f"{evalue}: {last_error}"
            if last_error is not None and self._UNAUTHORIZED_MARKER in last_error:
                login_returncode, _ = self._run_device_auth_login()
                if login_returncode == 0:
                    evalue = f"{evalue}\nDevice auth completed. Re-run this cell."
                else:
                    evalue = f"{evalue}\nDevice auth failed with status {login_returncode}."
            return {
                "status": "error",
                "ename": "CodexExecError",
                "evalue": evalue,
                "traceback": [f"Command failed: {' '.join(cmd)}"],
            }

        return {"status": "ok", "execution_count": self.execution_count, "payload": [], "user_expressions": {}}


def main() -> None:
    IPKernelApp.launch_instance(kernel_class=CodexKernel)


if __name__ == "__main__":
    main()
