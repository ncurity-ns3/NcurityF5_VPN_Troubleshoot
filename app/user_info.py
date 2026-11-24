"""In-memory + on-disk user-reported case info (for escalation)."""

from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.paths import troubleshoot_dir


@dataclass
class UserCaseInfo:
    user_id: str = ""
    issue_time: str = ""
    vpn_domain: str = ""
    os_note: str = ""
    symptom: str = ""
    note: str = ""
    saved_at: str = field(default="", repr=False)

    def is_complete(self) -> bool:
        return bool(self.user_id.strip() and self.issue_time.strip() and self.vpn_domain.strip())

    def to_text(self) -> str:
        lines = [
            "===== 사용자 정보 =====",
            f"사용자 계정 (ID) : {self.user_id}",
            f"이슈 발생 시간     : {self.issue_time}",
            f"VPN 접속 도메인    : {self.vpn_domain}",
            f"OS 버전            : {self.os_note}",
            f"증상 / 오류 메시지 : {self.symptom}",
            f"비고               : {self.note}",
            f"저장 시각          : {self.saved_at}",
            f"Windows 로그인 계정: {os.environ.get('USERNAME', '')}",
            f"컴퓨터 이름        : {os.environ.get('COMPUTERNAME', '')}",
            "",
        ]
        return "\n".join(lines)


_current = UserCaseInfo()


def get_user_info() -> UserCaseInfo:
    return _current


def set_user_info(info: UserCaseInfo) -> Path:
    global _current
    info.saved_at = time.strftime("%Y-%m-%d %H:%M:%S")
    _current = info
    base = troubleshoot_dir()
    path = base / "user_info.txt"
    path.write_text(info.to_text(), encoding="utf-8-sig")
    # Also keep a dated copy for multiple cases
    if info.user_id.strip():
        stamp = time.strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in info.user_id.strip())
        (base / f"user_info_{safe}_{stamp}.txt").write_text(info.to_text(), encoding="utf-8-sig")
    return path


def load_user_info_from_disk() -> UserCaseInfo | None:
    path = troubleshoot_dir() / "user_info.txt"
    if not path.exists():
        return None
    # Best-effort parse is optional; keep memory as source of truth after save
    return _current if _current.user_id else None


def as_dict() -> dict:
    return asdict(_current)
