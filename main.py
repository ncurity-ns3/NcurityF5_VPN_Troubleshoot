"""Entry point — elevate to admin, then show MainWindow (no console)."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from app import APP_NAME
from app.main_window import MainWindow
from app.paths import resource_path
from app.theme import apply_theme


def hide_console() -> None:
    """Hide the black python.exe console when launched from a console host."""
    if sys.platform != "win32":
        return
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:  # noqa: BLE001
        pass


def set_app_user_model_id() -> None:
    """Keep taskbar icon separate from python.exe grouping."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "F5.SSLVPN.TroubleshootTool"
        )
    except Exception:  # noqa: BLE001
        pass


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


def _pythonw_path() -> Path | None:
    """Prefer pythonw.exe so relaunch after UAC has no console."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        return exe
    candidate = exe.with_name("pythonw.exe")
    if candidate.exists():
        return candidate
    return None


def elevate_and_exit() -> None:
    # Prefer .pyw so elevated process also has no console
    root = Path(__file__).resolve().parent
    script = root / "main.pyw"
    if not script.exists():
        script = Path(__file__).resolve()
    if getattr(sys, "frozen", False):
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, "", None, 1)
        return

    launcher = str(_pythonw_path() or sys.executable)
    ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        launcher,
        f'"{script}"',
        None,
        1,
    )


def main() -> int:
    set_app_user_model_id()
    hide_console()

    if sys.platform == "win32" and not is_admin():
        try:
            elevate_and_exit()
        except Exception:  # noqa: BLE001
            pass
        else:
            return 0

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    apply_theme(app)

    icon_path = resource_path("branding", "app_icon.ico")
    if not icon_path.exists():
        icon_path = resource_path("branding", "app_icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    if sys.platform == "win32" and not is_admin():
        QMessageBox.warning(
            None,
            "관리자 권한 필요",
            "일부 조치(Miniport 삭제, 서비스 재시작, SFC 등)는 관리자 권한이 필요합니다.\n"
            "프로그램을 우클릭 → 관리자 권한으로 실행해 주세요.",
        )

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
