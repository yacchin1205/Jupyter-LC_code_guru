#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from ipykernel.kernelapp import IPKernelApp
from ipykernel.kernelbase import Kernel
from rich.console import Console
from rich.markdown import Markdown


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
    _LOGOUT_COMMAND = "%%logout"
    _CODE_THEME = "github-light"
    _ITEM_STARTED_COLOR = "\x1b[36m"
    _COLOR_RESET = "\x1b[0m"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._thread_id: str | None = None
        self._show_events = os.environ.get("CODEX_KERNEL_SHOW_EVENTS", "0") == "1"
        self._markdown_console = Console(force_terminal=True, color_system="auto", width=300)

    def _build_command(self, code: str) -> list[str]:
        if self._thread_id is None:
            return [
                "codex",
                "exec",
                "--full-auto",
                "--json",
                "--skip-git-repo-check",
                code,
            ]
        return [
            "codex",
            "exec",
            "resume",
            "--full-auto",
            "--json",
            "--skip-git-repo-check",
            self._thread_id,
            code,
        ]

    def _run_exec_and_stream(self, cmd: list[str], silent: bool) -> tuple[int, str | None]:
        last_error: str | None = None
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for line in proc.stdout:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                if not silent:
                    self.send_response(
                        self.iopub_socket,
                        "stream",
                        {"name": "stderr", "text": line},
                    )
                continue
            event_type = event["type"]
            if event_type == "thread.started":
                self._thread_id = event["thread_id"]
            elif event_type == "turn.started":
                pass
            elif event_type == "turn.completed":
                pass
            elif event_type == "item.started":
                if not silent:
                    item = event["item"]
                    item_type = item["type"]
                    message = f"Starting task: {item_type}"
                    if item_type == "command_execution":
                        message = f"{message}: {item['command']}"
                    self.send_response(
                        self.iopub_socket,
                        "stream",
                        {
                            "name": "stdout",
                            "text": f"{self._ITEM_STARTED_COLOR}{message}{self._COLOR_RESET}\n",
                        },
                    )
            elif event_type == "item.completed":
                item = event["item"]
                if item["type"] == "agent_message" and not silent:
                    markdown_text = self._render_markdown(item["text"])
                    self.send_response(
                        self.iopub_socket,
                        "stream",
                        {"name": "stdout", "text": markdown_text},
                    )
            elif event_type == "error":
                if not silent:
                    self.send_response(
                        self.iopub_socket,
                        "stream",
                        {"name": "stderr", "text": f"{event['message']}\n"},
                    )
            elif event_type == "turn.failed":
                last_error = event["error"]["message"]
            else:
                if not silent:
                    self.send_response(
                        self.iopub_socket,
                        "stream",
                        {"name": "stderr", "text": line},
                    )
            if self._show_events and not silent:
                self.send_response(
                    self.iopub_socket,
                    "stream",
                    {"name": "stdout", "text": f"{stripped}\n"},
                )
        return (proc.wait(), last_error)

    def _render_markdown(self, text: str) -> str:
        with self._markdown_console.capture() as capture:
            self._markdown_console.print(
                Markdown(
                    text,
                    code_theme=self._CODE_THEME,
                    inline_code_theme=self._CODE_THEME,
                    hyperlinks=False,
                )
            )
        return capture.get()

    def _run_device_auth_login(self) -> tuple[int, str]:
        proc = subprocess.Popen(
            ["codex", "login", "--device-auth"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        login_lines: list[str] = []
        for line in proc.stdout:
            login_lines.append(line.rstrip("\n"))
            self.send_response(
                self.iopub_socket,
                "stream",
                {"name": "stdout", "text": line},
            )
        returncode = proc.wait()
        return (returncode, "\n".join(login_lines))

    def _run_logout(self) -> tuple[int, str]:
        proc = subprocess.Popen(
            ["codex", "logout"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        logout_lines: list[str] = []
        for line in proc.stdout:
            logout_lines.append(line.rstrip("\n"))
            self.send_response(
                self.iopub_socket,
                "stream",
                {"name": "stdout", "text": line},
            )
        returncode = proc.wait()
        return (returncode, "\n".join(logout_lines))

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
        if code.strip() == self._LOGOUT_COMMAND:
            logout_returncode, _ = self._run_logout()
            if logout_returncode != 0:
                return {
                    "status": "error",
                    "ename": "CodexLogoutError",
                    "evalue": f"codex logout exited with status {logout_returncode}",
                    "traceback": [f"Command failed: codex logout"],
                }
            return {"status": "ok", "execution_count": self.execution_count, "payload": [], "user_expressions": {}}

        cmd = self._build_command(code)
        returncode, last_error = self._run_exec_and_stream(cmd, silent)

        if returncode != 0:
            evalue = f"codex exited with status {returncode}"
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
