"""Resource / output path helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    """Resolve a path under resources/ (works for source and PyInstaller)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS) / "resources"
    else:
        base = app_root() / "resources"
    return base.joinpath(*parts)


def desktop_dir() -> Path:
    # Prefer OneDrive Desktop when present; fall back to USERPROFILE\Desktop
    home = Path.home()
    candidates = [
        home / "Desktop",
        home / "OneDrive" / "Desktop",
        Path(os.path.expandvars(r"%USERPROFILE%\Desktop")),
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def troubleshoot_dir() -> Path:
    path = desktop_dir() / "F5_VPN_Troubleshoot"
    path.mkdir(parents=True, exist_ok=True)
    return path
