"""Silent Windows process helpers — no console flash."""

from __future__ import annotations

import subprocess
from typing import Sequence


def _flags() -> int:
    return subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0


def run_silent(
    cmd: Sequence[str],
    *,
    timeout: int | None = 30,
    cwd: str | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        list(cmd),
        capture_output=True,
        timeout=timeout,
        cwd=cwd,
        creationflags=_flags(),
    )


def popen_silent(cmd: Sequence[str], *, cwd: str | None = None) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        list(cmd),
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_flags(),
    )
