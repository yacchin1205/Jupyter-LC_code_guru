#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from jupyter_client.kernelspec import KernelSpecManager


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    kernel_entry = repo_root / "scripts" / "codex_kernel.py"
    if not kernel_entry.exists():
        raise FileNotFoundError(kernel_entry)

    spec = {
        "argv": [sys.executable, str(kernel_entry), "-f", "{connection_file}"],
        "display_name": "Codex",
        "language": "codex",
        "interrupt_mode": "message",
        "env": {"PYTHONUNBUFFERED": "1"},
    }

    with tempfile.TemporaryDirectory(prefix="codex-kernel-spec-") as tmp:
        spec_dir = Path(tmp)
        (spec_dir / "kernel.json").write_text(
            json.dumps(spec, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        manager = KernelSpecManager()
        destination = manager.install_kernel_spec(
            source_dir=str(spec_dir),
            kernel_name="codex",
            user=True,
        )

    print(f"Installed Codex kernel at: {destination}")
    print(f"Kernel entrypoint: {os.fspath(kernel_entry)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
