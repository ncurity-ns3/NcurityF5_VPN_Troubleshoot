"""Silent Windows process helpers — no console / PowerShell flash."""

from __future__ import annotations

import subprocess
from typing import Sequence

# Prevent console window creation for child processes
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_STARTF_USESHOWWINDOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 1)


def _startupinfo() -> subprocess.STARTUPINFO | None:
    if not hasattr(subprocess, "STARTUPINFO"):
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= _STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return si


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
        creationflags=_CREATE_NO_WINDOW,
        startupinfo=_startupinfo(),
    )


def popen_silent(cmd: Sequence[str], *, cwd: str | None = None) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        list(cmd),
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_CREATE_NO_WINDOW,
        startupinfo=_startupinfo(),
    )


def run_powershell_silent(script: str, *, timeout: int | None = 60) -> subprocess.CompletedProcess[bytes]:
    """Run PowerShell without a visible window (last resort — prefer non-PS tools)."""
    return run_silent(
        [
            "powershell.exe",
            "-NoProfile",
            "-NoLogo",
            "-NonInteractive",
            "-WindowStyle",
            "Hidden",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        timeout=timeout,
    )
